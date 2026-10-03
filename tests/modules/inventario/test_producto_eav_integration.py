from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy import Column, Table
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from osiris.core.db import get_session
from osiris.core.auth import get_current_usuario
from osiris.main import app
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.rol.entity import Rol
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.sri.tipo_contribuyente.entity import TipoContribuyente
from osiris.modules.inventario.atributo.entity import Atributo, TipoDato
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.producto.entity import (
    Producto,
    ProductoBodega,
    ProductoCategoria,
    ProductoImpuesto,
    ProductoProveedorPersona,
    ProductoProveedorSociedad,
    TipoProducto,
)
from osiris.modules.inventario.bodega.entity import Bodega
from osiris.modules.sri.impuesto_catalogo.entity import ImpuestoCatalogo
from osiris.modules.inventario.producto.models_atributos import ProductoAtributoValor


def _ensure_fk_stub_targets_in_metadata() -> None:
    if "tbl_proveedor_persona" not in SQLModel.metadata.tables:
        Table(
            "tbl_proveedor_persona",
            SQLModel.metadata,
            Column("id", sa.Uuid(), primary_key=True),
        )
    if "tbl_proveedor_sociedad" not in SQLModel.metadata.tables:
        Table(
            "tbl_proveedor_sociedad",
            SQLModel.metadata,
            Column("id", sa.Uuid(), primary_key=True),
        )


def _build_test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _ensure_fk_stub_targets_in_metadata()
    SQLModel.metadata.create_all(
        engine,
        tables=[
            AuditLog.__table__,
            TipoContribuyente.__table__,
            Rol.__table__,
            Empresa.__table__,
            Sucursal.__table__,
            Bodega.__table__,
            CasaComercial.__table__,
            Categoria.__table__,
            Atributo.__table__,
            CategoriaAtributo.__table__,
            Producto.__table__,
            ProductoBodega.__table__,
            ImpuestoCatalogo.__table__,
            ProductoImpuesto.__table__,
            ProductoCategoria.__table__,
            ProductoProveedorPersona.__table__,
            ProductoProveedorSociedad.__table__,
            ProductoAtributoValor.__table__,
        ],
    )
    return engine


def _seed_flujo_exito(session: Session):
    abuelo = Categoria(nombre=f"Abuelo-{uuid4().hex[:6]}", es_padre=True, usuario_auditoria="test")
    padre = Categoria(nombre=f"Padre-{uuid4().hex[:6]}", es_padre=True, parent_id=abuelo.id, usuario_auditoria="test")
    hijo = Categoria(nombre=f"Hijo-{uuid4().hex[:6]}", es_padre=False, parent_id=padre.id, usuario_auditoria="test")

    garantia = Atributo(nombre=f"Garantia-{uuid4().hex[:6]}", tipo_dato=TipoDato.STRING, usuario_auditoria="test")
    color = Atributo(nombre=f"Color-{uuid4().hex[:6]}", tipo_dato=TipoDato.STRING, usuario_auditoria="test")
    pulgadas = Atributo(nombre=f"Pulgadas-{uuid4().hex[:6]}", tipo_dato=TipoDato.INTEGER, usuario_auditoria="test")

    producto = Producto(
        nombre=f"Producto-{uuid4().hex[:6]}",
        tipo=TipoProducto.BIEN,
        pvp=Decimal("999.00"),
        usuario_auditoria="test",
    )

    session.add_all([abuelo, padre, hijo, garantia, color, pulgadas, producto])
    session.flush()

    session.add_all(
        [
            CategoriaAtributo(
                categoria_id=abuelo.id,
                atributo_id=garantia.id,
                obligatorio=False,
                orden=99,
                usuario_auditoria="test",
            ),
            CategoriaAtributo(
                categoria_id=padre.id,
                atributo_id=garantia.id,
                obligatorio=True,
                orden=1,
                usuario_auditoria="test",
            ),
            CategoriaAtributo(
                categoria_id=abuelo.id,
                atributo_id=color.id,
                obligatorio=False,
                orden=2,
                usuario_auditoria="test",
            ),
            CategoriaAtributo(
                categoria_id=hijo.id,
                atributo_id=pulgadas.id,
                obligatorio=False,
                orden=3,
                usuario_auditoria="test",
            ),
            ProductoCategoria(producto_id=producto.id, categoria_id=hijo.id),
        ]
    )
    session.commit()

    return producto.id, garantia.id, color.id, pulgadas.id


def _seed_flujo_rechazo(session: Session):
    raiz_a = Categoria(nombre=f"CatalogoA-{uuid4().hex[:6]}", es_padre=True, usuario_auditoria="test")
    hijo_a = Categoria(nombre=f"Laptops-{uuid4().hex[:6]}", es_padre=False, parent_id=raiz_a.id, usuario_auditoria="test")
    raiz_b = Categoria(nombre=f"CatalogoB-{uuid4().hex[:6]}", es_padre=True, usuario_auditoria="test")
    hijo_b = Categoria(nombre=f"Motos-{uuid4().hex[:6]}", es_padre=False, parent_id=raiz_b.id, usuario_auditoria="test")

    ram = Atributo(nombre=f"RAM-{uuid4().hex[:6]}", tipo_dato=TipoDato.STRING, usuario_auditoria="test")
    cilindrada = Atributo(nombre=f"Cilindrada-{uuid4().hex[:6]}", tipo_dato=TipoDato.INTEGER, usuario_auditoria="test")

    producto = Producto(
        nombre=f"Producto-{uuid4().hex[:6]}",
        tipo=TipoProducto.BIEN,
        pvp=Decimal("499.00"),
        usuario_auditoria="test",
    )

    session.add_all([raiz_a, hijo_a, raiz_b, hijo_b, ram, cilindrada, producto])
    session.flush()
    session.add_all(
        [
            CategoriaAtributo(
                categoria_id=hijo_a.id,
                atributo_id=ram.id,
                obligatorio=False,
                orden=1,
                usuario_auditoria="test",
            ),
            CategoriaAtributo(
                categoria_id=hijo_b.id,
                atributo_id=cilindrada.id,
                obligatorio=False,
                orden=1,
                usuario_auditoria="test",
            ),
            ProductoCategoria(producto_id=producto.id, categoria_id=hijo_a.id),
        ]
    )
    session.commit()
    return producto.id, cilindrada.id, cilindrada.nombre


def test_producto_eav_flujo_exito_heredar_validar_guardar_merge():
    engine = _build_test_engine()
    with Session(engine) as session:
        producto_id, garantia_id, color_id, pulgadas_id = _seed_flujo_exito(session)
        session.add(TipoContribuyente(codigo="01", nombre="Sociedad", activo=True))
        company = Empresa(
            razon_social="Empresa Test",
            ruc="1790012345001",
            direccion_matriz="Direccion",
            tipo_contribuyente_id="01",
            usuario_auditoria="test",
            activo=True,
        )
        role = Rol(nombre="admin", usuario_auditoria="test", activo=True)
        session.add_all([company, role])
        session.flush()
        branch = Sucursal(codigo="001", nombre="Matriz", direccion="Direccion", es_matriz=True, empresa_id=company.id, usuario_auditoria="test", activo=True)
        session.add(branch)
        session.flush()
        warehouse = Bodega(codigo_bodega="B1", nombre_bodega="Bodega", empresa_id=company.id, sucursal_id=branch.id, usuario_auditoria="test", activo=True)
        session.add(warehouse)
        session.flush()
        session.add(ProductoBodega(producto_id=producto_id, bodega_id=warehouse.id, cantidad=Decimal("0"), usuario_auditoria="test", activo=True))
        session.commit()
        company_id = str(company.id)
        role_id = role.id

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_usuario] = lambda: SimpleNamespace(rol_id=role_id)
    try:
        with TestClient(app) as client:
            put_resp = client.put(
                f"/api/v1/productos/{producto_id}/atributos",
                json=[
                    {"atributo_id": str(garantia_id), "valor": "24 meses"},
                    {"atributo_id": str(color_id), "valor": "Negro"},
                    {"atributo_id": str(pulgadas_id), "valor": "55"},
                ],
                headers={"X-Empresa-Id": company_id},
            )
            assert put_resp.status_code == 200
            saved = put_resp.json()
            assert len(saved) == 3

            get_resp = client.get(f"/api/v1/productos/{producto_id}", headers={"X-Empresa-Id": company_id})
            assert get_resp.status_code == 200
            body = get_resp.json()
            atributos = body.get("atributos", [])
            by_id = {item["atributo"]["id"]: item for item in atributos}

            assert str(garantia_id) in by_id
            assert by_id[str(garantia_id)]["valor"] == "24 meses"
            assert by_id[str(garantia_id)]["obligatorio"] is True
            assert by_id[str(garantia_id)]["orden"] == 1

            assert str(color_id) in by_id
            assert by_id[str(color_id)]["valor"] == "Negro"
            assert by_id[str(color_id)]["obligatorio"] is False

            assert str(pulgadas_id) in by_id
            assert by_id[str(pulgadas_id)]["valor"] == 55

            # Sin duplicados para el atributo heredado con conflicto.
            assert sum(1 for item in atributos if item["atributo"]["id"] == str(garantia_id)) == 1
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_usuario, None)


def test_producto_eav_flujo_rechazo_frontal_atributo_otra_rama():
    engine = _build_test_engine()
    with Session(engine) as session:
        producto_id, cilindrada_id, cilindrada_nombre = _seed_flujo_rechazo(session)
        session.add(TipoContribuyente(codigo="01", nombre="Sociedad", activo=True))
        company = Empresa(
            razon_social="Empresa Test",
            ruc="1790012345001",
            direccion_matriz="Direccion",
            tipo_contribuyente_id="01",
            usuario_auditoria="test",
            activo=True,
        )
        role = Rol(nombre="admin", usuario_auditoria="test", activo=True)
        session.add_all([company, role])
        session.flush()
        branch = Sucursal(codigo="001", nombre="Matriz", direccion="Direccion", es_matriz=True, empresa_id=company.id, usuario_auditoria="test", activo=True)
        session.add(branch)
        session.flush()
        warehouse = Bodega(codigo_bodega="B1", nombre_bodega="Bodega", empresa_id=company.id, sucursal_id=branch.id, usuario_auditoria="test", activo=True)
        session.add(warehouse)
        session.flush()
        session.add(ProductoBodega(producto_id=producto_id, bodega_id=warehouse.id, cantidad=Decimal("0"), usuario_auditoria="test", activo=True))
        session.commit()
        company_id = str(company.id)
        role_id = role.id

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_usuario] = lambda: SimpleNamespace(rol_id=role_id)
    try:
        with TestClient(app) as client:
            resp = client.put(
                f"/api/v1/productos/{producto_id}/atributos",
                json=[{"atributo_id": str(cilindrada_id), "valor": "150"}],
                headers={"X-Empresa-Id": company_id},
            )
            assert resp.status_code == 400
            detail = resp.json().get("detail", "")
            assert cilindrada_nombre in detail
            assert str(cilindrada_id) in detail
            assert "no aplica a las categorias actuales del producto" in detail
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_usuario, None)
