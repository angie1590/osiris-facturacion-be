from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy import Column, Table
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from osiris.core.db import get_session
from osiris.main import app
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.producto.entity import (
    Producto,
    ProductoCategoria,
    ProductoImpuesto,
    ProductoProveedorPersona,
    ProductoProveedorSociedad,
)
from osiris.modules.sri.impuesto_catalogo.entity import AplicaA, ImpuestoCatalogo, TipoImpuesto


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
            CasaComercial.__table__,
            Categoria.__table__,
            ImpuestoCatalogo.__table__,
            Producto.__table__,
            ProductoCategoria.__table__,
            ProductoImpuesto.__table__,
            ProductoProveedorPersona.__table__,
            ProductoProveedorSociedad.__table__,
        ],
    )
    return engine


def _seed_iva(session: Session) -> str:
    iva = ImpuestoCatalogo(
        tipo_impuesto=TipoImpuesto.IVA,
        codigo_tipo_impuesto="2",
        codigo_sri=f"IVA-{uuid4().hex[:6]}",
        descripcion="IVA Test",
        vigente_desde=date.today(),
        aplica_a=AplicaA.AMBOS,
        porcentaje_iva=12,
        usuario_auditoria="test",
        activo=True,
    )
    session.add(iva)
    session.commit()
    session.refresh(iva)
    return str(iva.id)


def test_regresion_bloqueo_nativo_producto_en_categoria_con_hijos():
    engine = _build_test_engine()
    with Session(engine) as session:
        iva_id = _seed_iva(session)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            r = client.post(
                "/api/v1/categorias",
                json={"nombre": f"A-{uuid4().hex[:6]}", "es_padre": True, "usuario_auditoria": "test"},
            )
            assert r.status_code == 201, r.text
            categoria_a_id = r.json()["id"]

            r = client.post(
                "/api/v1/categorias",
                json={
                    "nombre": f"B-{uuid4().hex[:6]}",
                    "es_padre": False,
                    "parent_id": categoria_a_id,
                    "usuario_auditoria": "test",
                },
            )
            assert r.status_code == 201, r.text

            r = client.post(
                "/api/v1/productos",
                json={
                    "nombre": f"Prod-NoLeaf-{uuid4().hex[:6]}",
                    "tipo": "BIEN",
                    "pvp": 10.50,
                    "categoria_ids": [categoria_a_id],
                    "impuesto_catalogo_ids": [iva_id],
                    "usuario_auditoria": "test",
                },
            )
            assert r.status_code == 400, r.text
            assert "Solo se permiten categorías hoja" in r.text
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_e2e_convivencia_b3_migra_a_general_y_producto_permanece_editable():
    engine = _build_test_engine()
    with Session(engine) as session:
        iva_id = _seed_iva(session)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            r = client.post(
                "/api/v1/categorias",
                json={"nombre": f"X-{uuid4().hex[:6]}", "es_padre": False, "usuario_auditoria": "test"},
            )
            assert r.status_code == 201, r.text
            categoria_x_id = r.json()["id"]
            categoria_x_uuid = UUID(categoria_x_id)

            r = client.post(
                "/api/v1/productos",
                json={
                    "nombre": f"Prod-B3-{uuid4().hex[:6]}",
                    "tipo": "BIEN",
                    "pvp": 22.75,
                    "categoria_ids": [categoria_x_id],
                    "impuesto_catalogo_ids": [iva_id],
                    "usuario_auditoria": "test",
                },
            )
            assert r.status_code == 201, r.text
            producto_id = r.json()["id"]

            r = client.post(
                "/api/v1/categorias",
                json={
                    "nombre": f"Y-{uuid4().hex[:6]}",
                    "es_padre": False,
                    "parent_id": categoria_x_id,
                    "usuario_auditoria": "test",
                },
            )
            assert r.status_code == 201, r.text

            with Session(engine) as session:
                general = session.exec(
                    select(Categoria)
                    .where(Categoria.parent_id == categoria_x_uuid)
                    .where(sa.func.lower(Categoria.nombre) == "general")
                ).first()
            assert general is not None
            general_id = str(general.id)

            r = client.get(f"/api/v1/productos/{producto_id}")
            assert r.status_code == 200, r.text
            body = r.json()
            categorias = body.get("categorias", [])
            assert any(cat.get("id") == general_id for cat in categorias), body

            r = client.put(
                f"/api/v1/productos/{producto_id}",
                json={
                    "nombre": f"Prod-B3-Updated-{uuid4().hex[:6]}",
                    "usuario_auditoria": "test",
                },
            )
            assert r.status_code == 200, r.text
    finally:
        app.dependency_overrides.pop(get_session, None)
