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
from osiris.modules.compras.models import Compra, CuentaPorPagar
from osiris.modules.sri.core_sri.types import (
    EstadoCompra,
    EstadoCuentaPorCobrar,
    EstadoCuentaPorPagar,
    EstadoVenta,
    FormaPagoSRI,
    SustentoTributarioSRI,
    TipoIdentificacionSRI,
)
from osiris.modules.ventas.models import CuentaPorCobrar, Venta


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
            Compra.__table__,
            CuentaPorPagar.__table__,
        ],
    )
    return engine


def _venta(cliente_id) -> Venta:
    return Venta(
        cliente_id=cliente_id,
        fecha_emision=date(2026, 2, 10),
        tipo_identificacion_comprador=TipoIdentificacionSRI.RUC,
        identificacion_comprador=f"{str(uuid4().int)[:13]}",
        forma_pago=FormaPagoSRI.EFECTIVO,
        subtotal_sin_impuestos=Decimal("50.00"),
        subtotal_12=Decimal("50.00"),
        subtotal_15=Decimal("0.00"),
        subtotal_0=Decimal("0.00"),
        subtotal_no_objeto=Decimal("0.00"),
        monto_iva=Decimal("6.00"),
        monto_ice=Decimal("0.00"),
        valor_total=Decimal("56.00"),
        estado=EstadoVenta.EMITIDA,
        usuario_auditoria="test",
        activo=True,
    )


def _compra(proveedor_id) -> Compra:
    return Compra(
        proveedor_id=proveedor_id,
        secuencial_factura=f"001-001-{str(uuid4().int)[-9:]}",
        autorizacion_sri=str(uuid4().int)[:37],
        fecha_emision=date(2026, 2, 11),
        sustento_tributario=SustentoTributarioSRI.CREDITO_TRIBUTARIO_BIENES,
        tipo_identificacion_proveedor=TipoIdentificacionSRI.RUC,
        identificacion_proveedor=f"{str(uuid4().int)[:13]}",
        forma_pago=FormaPagoSRI.TRANSFERENCIA,
        subtotal_sin_impuestos=Decimal("80.00"),
        subtotal_12=Decimal("80.00"),
        subtotal_15=Decimal("0.00"),
        subtotal_0=Decimal("0.00"),
        subtotal_no_objeto=Decimal("0.00"),
        monto_iva=Decimal("9.60"),
        monto_ice=Decimal("0.00"),
        valor_total=Decimal("89.60"),
        estado=EstadoCompra.REGISTRADA,
        usuario_auditoria="test",
        activo=True,
    )


def test_reporte_cartera_solo_pendientes():
    engine = _build_test_engine()
    with Session(engine) as session:
        cliente_pendiente = uuid4()
        cliente_saldado = uuid4()
        proveedor_pendiente = uuid4()
        proveedor_saldado = uuid4()

        venta_pendiente = _venta(cliente_pendiente)
        venta_saldada = _venta(cliente_saldado)
        session.add(venta_pendiente)
        session.add(venta_saldada)
        session.flush()

        session.add(
            CuentaPorCobrar(
                venta_id=venta_pendiente.id,
                valor_total_factura=Decimal("50.00"),
                valor_retenido=Decimal("0.00"),
                pagos_acumulados=Decimal("0.00"),
                saldo_pendiente=Decimal("50.00"),
                estado=EstadoCuentaPorCobrar.PENDIENTE,
                usuario_auditoria="test",
                activo=True,
            )
        )
        session.add(
            CuentaPorCobrar(
                venta_id=venta_saldada.id,
                valor_total_factura=Decimal("20.00"),
                valor_retenido=Decimal("0.00"),
                pagos_acumulados=Decimal("20.00"),
                saldo_pendiente=Decimal("0.00"),
                estado=EstadoCuentaPorCobrar.PAGADA,
                usuario_auditoria="test",
                activo=True,
            )
        )

        compra_pendiente = _compra(proveedor_pendiente)
        compra_saldada = _compra(proveedor_saldado)
        session.add(compra_pendiente)
        session.add(compra_saldada)
        session.flush()

        session.add(
            CuentaPorPagar(
                compra_id=compra_pendiente.id,
                valor_total_factura=Decimal("50.00"),
                valor_retenido=Decimal("0.00"),
                pagos_acumulados=Decimal("0.00"),
                saldo_pendiente=Decimal("50.00"),
                estado=EstadoCuentaPorPagar.PARCIAL,
                usuario_auditoria="test",
                activo=True,
            )
        )
        session.add(
            CuentaPorPagar(
                compra_id=compra_saldada.id,
                valor_total_factura=Decimal("30.00"),
                valor_retenido=Decimal("0.00"),
                pagos_acumulados=Decimal("30.00"),
                saldo_pendiente=Decimal("0.00"),
                estado=EstadoCuentaPorPagar.PAGADA,
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
            cobrar_response = client.get("/api/v1/reportes/cartera/cobrar")
            pagar_response = client.get("/api/v1/reportes/cartera/pagar")

        assert cobrar_response.status_code == 200, cobrar_response.text
        cobrar_data = cobrar_response.json()
        assert len(cobrar_data) == 1
        assert cobrar_data[0]["cliente_id"] == str(cliente_pendiente)
        assert Decimal(str(cobrar_data[0]["saldo_pendiente"])) == Decimal("50.00")

        assert pagar_response.status_code == 200, pagar_response.text
        pagar_data = pagar_response.json()
        assert len(pagar_data) == 1
        assert pagar_data[0]["proveedor_id"] == str(proveedor_pendiente)
        assert Decimal(str(pagar_data[0]["saldo_pendiente"])) == Decimal("50.00")
    finally:
        app.dependency_overrides.pop(get_session, None)
