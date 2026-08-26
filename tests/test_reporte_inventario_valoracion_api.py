from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from osiris.core.db import get_session
from osiris.main import app
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.inventario.movimientos.models import InventarioStock
from osiris.modules.inventario.bodega.entity import Bodega
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
            AuditLog.__table__,
            Empresa.__table__,
            Sucursal.__table__,
            Bodega.__table__,
            Producto.__table__,
            InventarioStock.__table__,
        ],
    )
    return engine


def test_reporte_valoracion_calcula_patrimonio():
    engine = _build_test_engine()
    with Session(engine) as session:
        tipo = TipoContribuyente(codigo="01", nombre="Sociedad", activo=True)
        session.add(tipo)
        empresa = Empresa(
            razon_social="Empresa Patrimonio",
            nombre_comercial="Empresa Patrimonio",
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
            codigo_bodega="BOD-PAT-1",
            nombre_bodega="Bodega Patrimonio",
            empresa_id=empresa.id,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(bodega)
        session.flush()

        prod_a = Producto(
            nombre="Producto A Patrimonio",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("0.00"),
            cantidad=0,
            usuario_auditoria="seed",
            activo=True,
        )
        prod_b = Producto(
            nombre="Producto B Patrimonio",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("0.00"),
            cantidad=0,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(prod_a)
        session.add(prod_b)
        session.flush()

        # 10 * 5 = 50
        session.add(
            InventarioStock(
                bodega_id=bodega.id,
                producto_id=prod_a.id,
                cantidad_actual=Decimal("10.0000"),
                costo_promedio_vigente=Decimal("5.0000"),
                usuario_auditoria="seed",
                activo=True,
            )
        )
        # 5 * 10 = 50
        session.add(
            InventarioStock(
                bodega_id=bodega.id,
                producto_id=prod_b.id,
                cantidad_actual=Decimal("5.0000"),
                costo_promedio_vigente=Decimal("10.0000"),
                usuario_auditoria="seed",
                activo=True,
            )
        )
        session.commit()

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/reportes/inventario/valoracion")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert Decimal(str(payload["patrimonio_total"])) == Decimal("100.00")
    finally:
        app.dependency_overrides.pop(get_session, None)
