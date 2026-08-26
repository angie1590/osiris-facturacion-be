from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from osiris.core.db import get_session
from osiris.main import app
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.sri.core_sri.models import (
    CuentaPorCobrar,
    EstadoCuentaPorCobrar,
    EstadoRetencionRecibida,
    FormaPagoSRI,
    RetencionRecibida,
    RetencionRecibidaEstadoHistorial,
    RetencionRecibidaDetalle,
    TipoIdentificacionSRI,
    Venta,
)
from osiris.modules.ventas.services.retencion_recibida_service import RetencionRecibidaService


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
            RetencionRecibidaEstadoHistorial.__table__,
        ],
    )
    return engine


def _crear_venta(session: Session, *, total: Decimal = Decimal("100.00")) -> Venta:
    venta = Venta(
        fecha_emision=date.today(),
        tipo_identificacion_comprador=TipoIdentificacionSRI.RUC,
        identificacion_comprador="1790012345001",
        forma_pago=FormaPagoSRI.EFECTIVO,
        subtotal_sin_impuestos=total,
        subtotal_12=Decimal("0.00"),
        subtotal_15=Decimal("0.00"),
        subtotal_0=total,
        subtotal_no_objeto=Decimal("0.00"),
        monto_iva=Decimal("0.00"),
        monto_ice=Decimal("0.00"),
        valor_total=total,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(venta)
    session.flush()
    return venta


def _crear_cxc(
    session: Session,
    *,
    venta_id,
    total: Decimal = Decimal("100.00"),
    retenido: Decimal = Decimal("0.00"),
    pagos: Decimal = Decimal("0.00"),
    saldo: Decimal = Decimal("100.00"),
    estado: EstadoCuentaPorCobrar = EstadoCuentaPorCobrar.PENDIENTE,
) -> CuentaPorCobrar:
    cxc = CuentaPorCobrar(
        venta_id=venta_id,
        valor_total_factura=total,
        valor_retenido=retenido,
        pagos_acumulados=pagos,
        saldo_pendiente=saldo,
        estado=estado,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(cxc)
    session.flush()
    return cxc


def _crear_retencion(
    session: Session,
    *,
    venta_id,
    total_retenido: Decimal,
    estado: EstadoRetencionRecibida = EstadoRetencionRecibida.BORRADOR,
) -> RetencionRecibida:
    retencion = RetencionRecibida(
        venta_id=venta_id,
        cliente_id=uuid4(),
        numero_retencion=f"001-001-{str(uuid4().int)[-9:]}",
        clave_acceso_sri=None,
        fecha_emision=date.today(),
        estado=estado,
        total_retenido=total_retenido,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(retencion)
    session.flush()
    return retencion


def test_aplicar_retencion_reduce_saldo():
    engine = _build_test_engine()
    service = RetencionRecibidaService()

    with Session(engine) as session:
        venta = _crear_venta(session, total=Decimal("100.00"))
        cxc = _crear_cxc(
            session,
            venta_id=venta.id,
            total=Decimal("100.00"),
            retenido=Decimal("0.00"),
            pagos=Decimal("0.00"),
            saldo=Decimal("100.00"),
            estado=EstadoCuentaPorCobrar.PENDIENTE,
        )
        retencion = _crear_retencion(session, venta_id=venta.id, total_retenido=Decimal("10.00"))
        session.commit()

        service.aplicar_retencion_recibida(session, retencion.id)

        session.refresh(cxc)
        session.refresh(retencion)
        assert cxc.valor_retenido == Decimal("10.00")
        assert cxc.saldo_pendiente == Decimal("90.00")
        assert cxc.estado == EstadoCuentaPorCobrar.PARCIAL
        assert retencion.estado == EstadoRetencionRecibida.APLICADA


def test_venta_pagada_mixta():
    engine = _build_test_engine()
    service = RetencionRecibidaService()

    with Session(engine) as session:
        venta = _crear_venta(session, total=Decimal("100.00"))
        cxc = _crear_cxc(
            session,
            venta_id=venta.id,
            total=Decimal("100.00"),
            retenido=Decimal("0.00"),
            pagos=Decimal("90.00"),
            saldo=Decimal("10.00"),
            estado=EstadoCuentaPorCobrar.PARCIAL,
        )
        retencion = _crear_retencion(session, venta_id=venta.id, total_retenido=Decimal("10.00"))
        session.commit()

        service.aplicar_retencion_recibida(session, retencion.id)

        session.refresh(cxc)
        session.refresh(retencion)
        assert cxc.valor_retenido == Decimal("10.00")
        assert cxc.saldo_pendiente == Decimal("0.00")
        assert cxc.estado == EstadoCuentaPorCobrar.PAGADA
        assert retencion.estado == EstadoRetencionRecibida.APLICADA


def test_bloqueo_retencion_excesiva():
    engine = _build_test_engine()
    service = RetencionRecibidaService()

    with Session(engine) as session:
        venta = _crear_venta(session, total=Decimal("100.00"))
        cxc = _crear_cxc(
            session,
            venta_id=venta.id,
            total=Decimal("100.00"),
            retenido=Decimal("0.00"),
            pagos=Decimal("0.00"),
            saldo=Decimal("100.00"),
            estado=EstadoCuentaPorCobrar.PENDIENTE,
        )
        retencion = _crear_retencion(session, venta_id=venta.id, total_retenido=Decimal("150.00"))
        session.commit()

        with pytest.raises(ValueError) as exc:
            service.aplicar_retencion_recibida(session, retencion.id)
        assert "la retención supera el saldo de la factura" in str(exc.value).lower()

        session.refresh(cxc)
        session.refresh(retencion)
        assert cxc.valor_retenido == Decimal("0.00")
        assert cxc.saldo_pendiente == Decimal("100.00")
        assert cxc.estado == EstadoCuentaPorCobrar.PENDIENTE
        assert retencion.estado == EstadoRetencionRecibida.BORRADOR


def test_anular_retencion_restaura_saldo():
    engine = _build_test_engine()
    service = RetencionRecibidaService()

    with Session(engine) as session:
        venta = _crear_venta(session, total=Decimal("100.00"))
        cxc = _crear_cxc(
            session,
            venta_id=venta.id,
            total=Decimal("100.00"),
            retenido=Decimal("10.00"),
            pagos=Decimal("0.00"),
            saldo=Decimal("90.00"),
            estado=EstadoCuentaPorCobrar.PARCIAL,
        )
        retencion = _crear_retencion(
            session,
            venta_id=venta.id,
            total_retenido=Decimal("10.00"),
            estado=EstadoRetencionRecibida.APLICADA,
        )
        session.commit()

        service.anular_retencion_recibida(
            session,
            retencion.id,
            motivo="Digitacion incorrecta",
            usuario_auditoria="contabilidad.user",
        )

        session.refresh(cxc)
        session.refresh(retencion)
        assert cxc.valor_retenido == Decimal("0.00")
        assert cxc.saldo_pendiente == Decimal("100.00")
        assert cxc.estado == EstadoCuentaPorCobrar.PENDIENTE
        assert retencion.estado == EstadoRetencionRecibida.ANULADA

        historial = session.exec(
            select(RetencionRecibidaEstadoHistorial).where(
                RetencionRecibidaEstadoHistorial.entidad_id == retencion.id
            )
        ).all()
        assert len(historial) == 1
        assert historial[0].motivo_cambio == "Digitacion incorrecta"


def test_anular_requiere_motivo():
    engine = _build_test_engine()
    retencion_id = None
    with Session(engine) as session:
        venta = _crear_venta(session, total=Decimal("100.00"))
        _crear_cxc(
            session,
            venta_id=venta.id,
            total=Decimal("100.00"),
            retenido=Decimal("10.00"),
            pagos=Decimal("0.00"),
            saldo=Decimal("90.00"),
            estado=EstadoCuentaPorCobrar.PARCIAL,
        )
        retencion = _crear_retencion(
            session,
            venta_id=venta.id,
            total_retenido=Decimal("10.00"),
            estado=EstadoRetencionRecibida.APLICADA,
        )
        session.commit()
        retencion_id = retencion.id

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/retenciones-recibidas/{retencion_id}/anular",
            json={"usuario_auditoria": "contabilidad.user"},
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.pop(get_session, None)
