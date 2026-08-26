from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from osiris.core.db import get_session
from osiris.main import app
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.inventario.bodega.entity import Bodega
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.movimientos.models import (
    InventarioStock,
    MovimientoInventario,
    MovimientoInventarioDetalle,
)
from osiris.modules.inventario.producto.entity import Producto, TipoProducto
from osiris.modules.sri.tipo_contribuyente.entity import TipoContribuyente


def _build_test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(
        engine,
        tables=[
            TipoContribuyente.__table__,
            Empresa.__table__,
            Sucursal.__table__,
            Bodega.__table__,
            CasaComercial.__table__,
            Producto.__table__,
            MovimientoInventario.__table__,
            MovimientoInventarioDetalle.__table__,
            InventarioStock.__table__,
            AuditLog.__table__,
        ],
    )
    return engine


def test_ajuste_requiere_motivo():
    engine = _build_test_engine()

    with Session(engine) as session:
        tipo = TipoContribuyente(codigo="01", nombre="Sociedad", activo=True)
        session.add(tipo)

        empresa = Empresa(
            razon_social="Empresa Ajuste",
            nombre_comercial="Empresa Ajuste",
            ruc="1790012345001",
            direccion_matriz="Av. Central",
            telefono="022345678",
            obligado_contabilidad=True,
            regimen="GENERAL",
            modo_emision="ELECTRONICO",
            tipo_contribuyente_id="01",
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(empresa)
        session.flush()

        bodega = Bodega(
            codigo_bodega="BOD-AJ-001",
            nombre_bodega="Bodega Ajuste",
            empresa_id=empresa.id,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(bodega)

        producto = Producto(
            nombre="Producto Ajuste",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            cantidad=0,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(producto)
        session.commit()
        bodega_id = str(bodega.id)
        producto_id = str(producto.id)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            crear = client.post(
                "/api/v1/inventarios/movimientos",
                json={
                    "bodega_id": bodega_id,
                    "tipo_movimiento": "AJUSTE",
                    "usuario_auditoria": "auditor.inventario",
                    "detalles": [
                        {
                            "producto_id": producto_id,
                            "cantidad": "3.0000",
                            "costo_unitario": "4.5000",
                        }
                    ],
                },
            )
            assert crear.status_code == 201
            movimiento_id = crear.json()["id"]

            confirmar = client.post(
                f"/api/v1/inventarios/movimientos/{movimiento_id}/confirmar",
                json={},
            )

        assert confirmar.status_code == 400
        assert "motivo_ajuste es obligatorio" in confirmar.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_session, None)
