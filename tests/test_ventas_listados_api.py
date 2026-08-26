from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from osiris.core.db import get_session
from osiris.main import app
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.sri.core_sri.types import (
    EstadoCuentaPorCobrar,
    EstadoRetencionRecibida,
    EstadoSriDocumento,
    EstadoVenta,
    FormaPagoSRI,
    TipoEmisionVenta,
    TipoIdentificacionSRI,
)
from osiris.modules.ventas.models import CuentaPorCobrar, RetencionRecibida, RetencionRecibidaDetalle, Venta



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
            Venta.__table__,
            CuentaPorCobrar.__table__,
            RetencionRecibida.__table__,
            RetencionRecibidaDetalle.__table__,
        ],
    )
    return engine



def _crear_venta(*, estado: EstadoVenta, secuencial: str) -> Venta:
    return Venta(
        cliente_id=uuid4(),
        fecha_emision=date(2026, 2, 25),
        secuencial_formateado=secuencial,
        tipo_identificacion_comprador=TipoIdentificacionSRI.RUC,
        identificacion_comprador="1790012345001",
        forma_pago=FormaPagoSRI.EFECTIVO,
        tipo_emision=TipoEmisionVenta.ELECTRONICA,
        subtotal_sin_impuestos=Decimal("100.00"),
        subtotal_12=Decimal("0.00"),
        subtotal_15=Decimal("100.00"),
        subtotal_0=Decimal("0.00"),
        subtotal_no_objeto=Decimal("0.00"),
        monto_iva=Decimal("15.00"),
        monto_ice=Decimal("0.00"),
        valor_total=Decimal("115.00"),
        estado=estado,
        estado_sri=EstadoSriDocumento.PENDIENTE,
        usuario_auditoria="test",
        activo=True,
    )



def test_listar_ventas_devuelve_campos_principales():
    engine = _build_test_engine()
    with Session(engine) as session:
        session.add(_crear_venta(estado=EstadoVenta.BORRADOR, secuencial="001-001-000000123"))
        session.add(_crear_venta(estado=EstadoVenta.EMITIDA, secuencial="001-001-000000124"))
        session.commit()

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/ventas", params={"limit": 10, "offset": 0})

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["meta"]["total"] == 2
        assert len(body["items"]) == 2
        first = body["items"][0]
        assert "fecha_emision" in first
        assert "cliente" in first
        assert "numero_factura" in first
        assert "valor_total" in first
    finally:
        app.dependency_overrides.pop(get_session, None)



def test_listar_retenciones_recibidas_y_obtener_detalle():
    engine = _build_test_engine()
    with Session(engine) as session:
        venta = _crear_venta(estado=EstadoVenta.EMITIDA, secuencial="001-001-000000125")
        session.add(venta)
        session.flush()

        retencion = RetencionRecibida(
            venta_id=venta.id,
            cliente_id=uuid4(),
            numero_retencion="001-001-000000777",
            fecha_emision=date(2026, 2, 25),
            estado=EstadoRetencionRecibida.BORRADOR,
            total_retenido=Decimal("5.00"),
            usuario_auditoria="test",
            activo=True,
        )
        session.add(retencion)
        session.flush()

        session.add(
            RetencionRecibidaDetalle(
                retencion_recibida_id=retencion.id,
                codigo_impuesto_sri="1",
                porcentaje_aplicado=Decimal("1.00"),
                base_imponible=Decimal("100.00"),
                valor_retenido=Decimal("5.00"),
                usuario_auditoria="test",
                activo=True,
            )
        )
        session.commit()
        retencion_id = retencion.id

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            listado = client.get("/api/v1/retenciones-recibidas", params={"limit": 10, "offset": 0})
            detalle = client.get(f"/api/v1/retenciones-recibidas/{retencion_id}")

        assert listado.status_code == 200, listado.text
        body = listado.json()
        assert body["meta"]["total"] == 1
        assert body["items"][0]["numero_retencion"] == "001-001-000000777"

        assert detalle.status_code == 200, detalle.text
        det = detalle.json()
        assert det["id"] == str(retencion_id)
        assert len(det["detalles"]) == 1
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_listar_cxc_devuelve_paginacion_y_campos_principales():
    engine = _build_test_engine()
    with Session(engine) as session:
        venta = _crear_venta(estado=EstadoVenta.EMITIDA, secuencial="001-001-000000200")
        session.add(venta)
        session.flush()
        session.add(
            CuentaPorCobrar(
                venta_id=venta.id,
                valor_total_factura=Decimal("115.00"),
                valor_retenido=Decimal("0.00"),
                pagos_acumulados=Decimal("15.00"),
                saldo_pendiente=Decimal("100.00"),
                estado=EstadoCuentaPorCobrar.PARCIAL,
                usuario_auditoria="test",
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
            response = client.get("/api/v1/cxc", params={"limit": 10, "offset": 0})

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["meta"]["total"] == 1
        item = body["items"][0]
        assert item["numero_factura"] == "001-001-000000200"
        assert item["cliente"] == "1790012345001"
        assert item["saldo_pendiente"] == "100.00"
        assert item["estado"] == "PARCIAL"
    finally:
        app.dependency_overrides.pop(get_session, None)
