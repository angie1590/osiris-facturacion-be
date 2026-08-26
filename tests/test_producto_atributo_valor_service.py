from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from osiris.core.db import get_session
from osiris.main import app
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
            CasaComercial.__table__,
            Producto.__table__,
            Categoria.__table__,
            CategoriaAtributo.__table__,
            ProductoCategoria.__table__,
            Atributo.__table__,
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


def test_endpoint_upsert_producto_atributos_e2e_ok():
    engine = _build_test_engine()

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
