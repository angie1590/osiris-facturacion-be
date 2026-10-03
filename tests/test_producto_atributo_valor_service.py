from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from osiris.core.db import get_session
from osiris.core.auth import get_current_usuario
from osiris.main import app
from osiris.modules.common.catalogo.entity import Catalogo, CatalogoValor
from osiris.modules.common.rol.entity import Rol
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.inventario.atributo.entity import Atributo, TipoDato
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.producto.entity import Producto, ProductoCategoria, TipoProducto
from osiris.modules.inventario.producto.models_atributos import (
    ProductoAtributoValor,
    ProductoAtributoValorUpsert,
)
from osiris.modules.inventario.producto.service_atributos import ProductoAtributoValorService


def _build_test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(
        engine,
        tables=[
            AuditLog.__table__,
            Rol.__table__,
            CasaComercial.__table__,
            Producto.__table__,
            Categoria.__table__,
            CategoriaAtributo.__table__,
            ProductoCategoria.__table__,
            Atributo.__table__,
            Catalogo.__table__,
            CatalogoValor.__table__,
            ProductoAtributoValor.__table__,
        ],
    )
    return engine


def _seed_producto_y_atributo(session: Session, tipo_dato: TipoDato) -> tuple[Producto, Atributo]:
    producto = Producto(
        nombre=f"Producto-{uuid4().hex[:8]}",
        tipo=TipoProducto.BIEN,
        pvp=Decimal("10.00"),
        usuario_auditoria="tester",
        activo=True,
    )
    atributo = Atributo(
        nombre=f"Atributo-{uuid4().hex[:8]}",
        tipo_dato=tipo_dato,
        usuario_auditoria="tester",
        activo=True,
    )
    session.add(producto)
    session.add(atributo)
    session.commit()
    session.refresh(producto)
    session.refresh(atributo)
    return producto, atributo


def test_upsert_valores_producto_rechaza_tipo_invalido_integer():
    engine = _build_test_engine()
    service = ProductoAtributoValorService()

    with Session(engine) as session:
        producto, atributo_integer = _seed_producto_y_atributo(session, TipoDato.INTEGER)

        with pytest.raises(HTTPException) as exc:
            service.upsert_valores_producto(
                session,
                producto.id,
                [ProductoAtributoValorUpsert(atributo_id=atributo_integer.id, valor="hola")],
            )

        assert exc.value.status_code == 400
        assert exc.value.detail == (
            f"Valor incompatible para el atributo {atributo_integer.nombre}. "
            "Se esperaba un tipo integer."
        )


def test_upsert_valores_producto_asigna_columna_sql_correcta():
    engine = _build_test_engine()
    service = ProductoAtributoValorService()

    with Session(engine) as session:
        producto, atributo_integer = _seed_producto_y_atributo(session, TipoDato.INTEGER)

        service.upsert_valores_producto(
            session,
            producto.id,
            [ProductoAtributoValorUpsert(atributo_id=atributo_integer.id, valor="123")],
        )

        row = session.exec(
            select(ProductoAtributoValor)
            .where(ProductoAtributoValor.producto_id == producto.id)
            .where(ProductoAtributoValor.atributo_id == atributo_integer.id)
        ).first()

        assert row is not None
        assert row.valor_integer == 123
        assert row.valor_string is None
        assert row.valor_decimal is None
        assert row.valor_boolean is None
        assert row.valor_date is None


def test_upsert_select_normalizes_option_and_rejects_unknown_value():
    engine = _build_test_engine()
    service = ProductoAtributoValorService()

    with Session(engine) as session:
        product, attribute = _seed_producto_y_atributo(session, TipoDato.SELECT)
        attribute.select_options = ["Rojo", "Azul"]
        session.add(attribute)
        session.commit()

        service.upsert_valores_producto(
            session,
            product.id,
            [ProductoAtributoValorUpsert(atributo_id=attribute.id, valor="ROJO")],
        )
        row = session.exec(
            select(ProductoAtributoValor).where(
                ProductoAtributoValor.producto_id == product.id,
                ProductoAtributoValor.atributo_id == attribute.id,
            )
        ).one()
        assert row.valor_string == "Rojo"

        with pytest.raises(HTTPException, match="tipo select"):
            service.upsert_valores_producto(
                session,
                product.id,
                [ProductoAtributoValorUpsert(atributo_id=attribute.id, valor="Verde")],
            )


def test_upsert_catalog_requires_active_catalog_value():
    engine = _build_test_engine()
    service = ProductoAtributoValorService()

    with Session(engine) as session:
        product, attribute = _seed_producto_y_atributo(session, TipoDato.CATALOG)
        catalog = Catalogo(nombre=f"Marcas-{uuid4().hex[:6]}", usuario_auditoria="tester", activo=True)
        session.add(catalog)
        session.flush()
        catalog_value = CatalogoValor(
            catalogo_id=catalog.id,
            valor="Acme",
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(catalog_value)
        attribute.catalog_id = catalog.id
        session.add(attribute)
        session.commit()

        service.upsert_valores_producto(
            session,
            product.id,
            [ProductoAtributoValorUpsert(atributo_id=attribute.id, valor="Acme")],
        )
        with pytest.raises(HTTPException, match="tipo catalog"):
            service.upsert_valores_producto(
                session,
                product.id,
                [ProductoAtributoValorUpsert(atributo_id=attribute.id, valor="Unknown")],
            )


def test_upsert_numeric_attribute_respects_allow_negative():
    engine = _build_test_engine()
    service = ProductoAtributoValorService()

    with Session(engine) as session:
        product, attribute = _seed_producto_y_atributo(session, TipoDato.INTEGER)
        with pytest.raises(HTTPException, match="tipo integer"):
            service.upsert_valores_producto(
                session,
                product.id,
                [ProductoAtributoValorUpsert(atributo_id=attribute.id, valor=-1)],
            )

        attribute.allow_negative = True
        attribute.min_value = Decimal("-5")
        session.add(attribute)
        session.commit()
        service.upsert_valores_producto(
            session,
            product.id,
            [ProductoAtributoValorUpsert(atributo_id=attribute.id, valor=-1)],
        )
        row = session.exec(
            select(ProductoAtributoValor).where(ProductoAtributoValor.atributo_id == attribute.id)
        ).one()
        assert row.valor_integer == -1


def test_required_attribute_default_is_saved_when_upsert_omits_value():
    engine = _build_test_engine()
    service = ProductoAtributoValorService()

    with Session(engine) as session:
        product, attribute = _seed_producto_y_atributo(session, TipoDato.STRING)
        category = Categoria(
            nombre=f"Categoria-{uuid4().hex[:8]}",
            es_padre=False,
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(category)
        session.flush()
        session.add_all(
            [
                ProductoCategoria(producto_id=product.id, categoria_id=category.id),
                CategoriaAtributo(
                    categoria_id=category.id,
                    atributo_id=attribute.id,
                    obligatorio=True,
                    valor_default="N/A",
                    usuario_auditoria="tester",
                    activo=True,
                ),
            ]
        )
        session.commit()

        service.upsert_valores_producto_validando_aplicabilidad(session, product.id, [])

        row = session.exec(
            select(ProductoAtributoValor).where(
                ProductoAtributoValor.producto_id == product.id,
                ProductoAtributoValor.atributo_id == attribute.id,
            )
        ).one()
        assert row.valor_string == "N/A"


def test_required_attribute_without_default_rejects_missing_value():
    engine = _build_test_engine()
    service = ProductoAtributoValorService()

    with Session(engine) as session:
        product, attribute = _seed_producto_y_atributo(session, TipoDato.STRING)
        category = Categoria(
            nombre=f"Categoria-{uuid4().hex[:8]}",
            es_padre=False,
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(category)
        session.flush()
        session.add_all(
            [
                ProductoCategoria(producto_id=product.id, categoria_id=category.id),
                CategoriaAtributo(
                    categoria_id=category.id,
                    atributo_id=attribute.id,
                    obligatorio=True,
                    valor_default=None,
                    usuario_auditoria="tester",
                    activo=True,
                ),
            ]
        )
        session.commit()

        with pytest.raises(HTTPException, match="obligatorio y no tiene valor por defecto"):
            service.upsert_valores_producto_validando_aplicabilidad(session, product.id, [])


def test_endpoint_upsert_producto_atributos_e2e_ok():
    engine = _build_test_engine()
    with Session(engine) as session:
        admin_role = Rol(nombre="admin", usuario_auditoria="tester", activo=True)
        session.add(admin_role)
        session.commit()
        admin_role_id = admin_role.id

    with Session(engine) as session:
        producto, atributo_integer = _seed_producto_y_atributo(session, TipoDato.INTEGER)
        categoria = Categoria(
            nombre=f"Categoria-{uuid4().hex[:8]}",
            es_padre=False,
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(categoria)
        session.commit()
        session.refresh(categoria)
        session.add(
            ProductoCategoria(
                producto_id=producto.id,
                categoria_id=categoria.id,
            )
        )
        session.add(
            CategoriaAtributo(
                categoria_id=categoria.id,
                atributo_id=atributo_integer.id,
                obligatorio=False,
                usuario_auditoria="tester",
                activo=True,
            )
        )
        session.commit()
        producto_id = str(producto.id)
        atributo_id = str(atributo_integer.id)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_usuario] = lambda: SimpleNamespace(rol_id=admin_role_id)
    try:
        with TestClient(app) as client:
            response = client.put(
                f"/api/v1/productos/{producto_id}/atributos",
                json=[{"atributo_id": atributo_id, "valor": "77"}],
            )
            assert response.status_code == 200
            body = response.json()
            assert isinstance(body, list)
            assert body[0]["atributo_id"] == atributo_id
            assert body[0]["valor_integer"] == 77
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_usuario, None)


def test_upsert_valores_producto_rechaza_atributo_no_aplicable():
    engine = _build_test_engine()
    service = ProductoAtributoValorService()

    with Session(engine) as session:
        producto = Producto(
            nombre=f"Laptop-{uuid4().hex[:8]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            usuario_auditoria="tester",
            activo=True,
        )
        categoria_laptop = Categoria(
            nombre=f"Laptops-{uuid4().hex[:8]}",
            es_padre=False,
            usuario_auditoria="tester",
            activo=True,
        )
        categoria_motos = Categoria(
            nombre=f"Motos-{uuid4().hex[:8]}",
            es_padre=False,
            usuario_auditoria="tester",
            activo=True,
        )
        atributo_ram = Atributo(
            nombre=f"RAM-{uuid4().hex[:8]}",
            tipo_dato=TipoDato.STRING,
            usuario_auditoria="tester",
            activo=True,
        )
        atributo_cilindrada = Atributo(
            nombre=f"Cilindrada-{uuid4().hex[:8]}",
            tipo_dato=TipoDato.INTEGER,
            usuario_auditoria="tester",
            activo=True,
        )
        session.add_all(
            [
                producto,
                categoria_laptop,
                categoria_motos,
                atributo_ram,
                atributo_cilindrada,
            ]
        )
        session.commit()
        session.refresh(producto)
        session.refresh(categoria_laptop)
        session.refresh(categoria_motos)
        session.refresh(atributo_ram)
        session.refresh(atributo_cilindrada)

        session.add(
            ProductoCategoria(
                producto_id=producto.id,
                categoria_id=categoria_laptop.id,
            )
        )
        session.add(
            CategoriaAtributo(
                categoria_id=categoria_laptop.id,
                atributo_id=atributo_ram.id,
                obligatorio=False,
                usuario_auditoria="tester",
                activo=True,
            )
        )
        session.add(
            CategoriaAtributo(
                categoria_id=categoria_motos.id,
                atributo_id=atributo_cilindrada.id,
                obligatorio=False,
                usuario_auditoria="tester",
                activo=True,
            )
        )
        session.commit()

        with pytest.raises(HTTPException) as exc:
            service.upsert_valores_producto_validando_aplicabilidad(
                session,
                producto.id,
                [ProductoAtributoValorUpsert(atributo_id=atributo_cilindrada.id, valor="150")],
            )

        assert exc.value.status_code == 400
        assert exc.value.detail == (
            f"El atributo {atributo_cilindrada.nombre} ({atributo_cilindrada.id}) "
            "no aplica a las categorias actuales del producto."
        )
