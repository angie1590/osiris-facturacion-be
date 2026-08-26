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
from osiris.modules.inventario.movimientos.models import InventarioStock
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
            Producto.__table__,
            InventarioStock.__table__,
            AuditLog.__table__,
        ],
    )
    return engine


def test_endpoint_valoracion_total():
    engine = _build_test_engine()

    with Session(engine) as session:
        tipo = TipoContribuyente(codigo="01", nombre="Sociedad", activo=True)
        session.add(tipo)

        empresa = Empresa(
            razon_social="Empresa Valoracion",
            nombre_comercial="Empresa Valoracion",
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

        bodega_1 = Bodega(
            codigo_bodega="BOD-VAL-1",
            nombre_bodega="Bodega Uno",
            empresa_id=empresa.id,
            usuario_auditoria="seed",
            activo=True,
        )
        bodega_2 = Bodega(
            codigo_bodega="BOD-VAL-2",
            nombre_bodega="Bodega Dos",
            empresa_id=empresa.id,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(bodega_1)
        session.add(bodega_2)
        session.flush()

        producto_1 = Producto(
            nombre="Producto Val 1",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            cantidad=0,
            usuario_auditoria="seed",
            activo=True,
        )
        producto_2 = Producto(
            nombre="Producto Val 2",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("20.00"),
            cantidad=0,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(producto_1)
        session.add(producto_2)
        session.flush()

        # Bodega 1: (10 * 2.00) + (5 * 3.00) = 35.00
        # Bodega 2: (4 * 2.50) = 10.00
        # Total global = 45.00
        session.add(
            InventarioStock(
                bodega_id=bodega_1.id,
                producto_id=producto_1.id,
                cantidad_actual=Decimal("10.0000"),
                costo_promedio_vigente=Decimal("2.0000"),
                usuario_auditoria="seed",
                activo=True,
            )
        )
        session.add(
            InventarioStock(
                bodega_id=bodega_1.id,
                producto_id=producto_2.id,
                cantidad_actual=Decimal("5.0000"),
                costo_promedio_vigente=Decimal("3.0000"),
                usuario_auditoria="seed",
                activo=True,
            )
        )
        session.add(
            InventarioStock(
                bodega_id=bodega_2.id,
                producto_id=producto_1.id,
                cantidad_actual=Decimal("4.0000"),
                costo_promedio_vigente=Decimal("2.5000"),
                usuario_auditoria="seed",
                activo=True,
            )
        )
        session.commit()
        bodega_1_id = str(bodega_1.id)
        bodega_2_id = str(bodega_2.id)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/inventarios/valoracion")
        assert response.status_code == 200
        payload = response.json()

        assert Decimal(str(payload["total_global"])) == Decimal("45.0000")
        bodegas = {row["bodega_id"]: row for row in payload["bodegas"]}
        assert Decimal(str(bodegas[bodega_1_id]["total_bodega"])) == Decimal("35.0000")
        assert Decimal(str(bodegas[bodega_2_id]["total_bodega"])) == Decimal("10.0000")
    finally:
        app.dependency_overrides.pop(get_session, None)
