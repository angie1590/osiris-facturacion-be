from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.punto_emision.entity import PuntoEmision
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.ventas.services.cxc_service import CuentaPorCobrarService
from osiris.modules.sri.core_sri.models import (
    CuentaPorCobrar,
    EstadoCuentaPorCobrar,
    FormaPagoSRI,
    PagoCxC,
    TipoIdentificacionSRI,
    Venta,
)
from osiris.modules.sri.tipo_contribuyente.entity import TipoContribuyente
from osiris.modules.sri.core_sri.all_schemas import PagoCxCCreate


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
            PuntoEmision.__table__,
            Venta.__table__,
            CuentaPorCobrar.__table__,
            PagoCxC.__table__,
        ],
    )
    return engine


def _crear_cxc(
    session: Session,
    *,
    total: Decimal = Decimal("100.00"),
    retenido: Decimal = Decimal("0.00"),
    pagos: Decimal = Decimal("0.00"),
    saldo: Decimal = Decimal("100.00"),
    estado: EstadoCuentaPorCobrar = EstadoCuentaPorCobrar.PENDIENTE,
) -> CuentaPorCobrar:
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

    cxc = CuentaPorCobrar(
        venta_id=venta.id,
        valor_total_factura=total,
        valor_retenido=retenido,
        pagos_acumulados=pagos,
        saldo_pendiente=saldo,
        estado=estado,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(cxc)
    session.commit()
    session.refresh(cxc)
    return cxc


def test_cxc_bloqueo_sobrepago():
    engine = _build_test_engine()
    service = CuentaPorCobrarService()

    with Session(engine) as session:
        cxc = _crear_cxc(session, total=Decimal("100.00"), saldo=Decimal("100.00"))

        with pytest.raises(HTTPException) as exc:
            service.registrar_pago_cxc(
                session,
                cxc.id,
                PagoCxCCreate(
                    monto=Decimal("120.00"),
                    fecha=date.today(),
                    forma_pago_sri=FormaPagoSRI.TRANSFERENCIA,
                    usuario_auditoria="cobros.user",
                ),
            )

        assert exc.value.status_code == 400
        assert "no puede ser mayor al saldo pendiente" in str(exc.value.detail).lower()

        session.refresh(cxc)
        assert cxc.pagos_acumulados == Decimal("0.00")
        assert cxc.saldo_pendiente == Decimal("100.00")
        assert cxc.estado == EstadoCuentaPorCobrar.PENDIENTE


def test_cxc_pago_parcial_y_total():
    engine = _build_test_engine()
    service = CuentaPorCobrarService()

    with Session(engine) as session:
        cxc = _crear_cxc(session, total=Decimal("100.00"), saldo=Decimal("100.00"))

        service.registrar_pago_cxc(
            session,
            cxc.id,
            PagoCxCCreate(
                monto=Decimal("50.00"),
                fecha=date.today(),
                forma_pago_sri=FormaPagoSRI.EFECTIVO,
                usuario_auditoria="cobros.user",
            ),
        )

        session.refresh(cxc)
        assert cxc.saldo_pendiente == Decimal("50.00")
        assert cxc.estado == EstadoCuentaPorCobrar.PARCIAL

        service.registrar_pago_cxc(
            session,
            cxc.id,
            PagoCxCCreate(
                monto=Decimal("50.00"),
                fecha=date.today(),
                forma_pago_sri=FormaPagoSRI.TRANSFERENCIA,
                usuario_auditoria="cobros.user",
            ),
        )

        session.refresh(cxc)
        assert cxc.pagos_acumulados == Decimal("100.00")
        assert cxc.saldo_pendiente == Decimal("0.00")
        assert cxc.estado == EstadoCuentaPorCobrar.PAGADA

        pagos = session.exec(select(PagoCxC).where(PagoCxC.cuenta_por_cobrar_id == cxc.id)).all()
        assert len(pagos) == 2


def test_registrar_pago_cxc_usa_bloqueo_pesimista():
    session = MagicMock()
    service = CuentaPorCobrarService()

    cxc_id = uuid4()
    cxc = CuentaPorCobrar(
        id=cxc_id,
        venta_id=uuid4(),
        valor_total_factura=Decimal("100.00"),
        valor_retenido=Decimal("0.00"),
        pagos_acumulados=Decimal("0.00"),
        saldo_pendiente=Decimal("100.00"),
        estado=EstadoCuentaPorCobrar.PENDIENTE,
        usuario_auditoria="seed",
        activo=True,
    )
    scalar_result = MagicMock()
    scalar_result.one_or_none.return_value = cxc
    session.exec.return_value = scalar_result

    pago = service.registrar_pago_cxc(
        session,
        cxc_id,
        PagoCxCCreate(
            monto=Decimal("20.00"),
            fecha=date.today(),
            forma_pago_sri=FormaPagoSRI.EFECTIVO,
            usuario_auditoria="cobros.user",
        ),
        commit=False,
    )

    session.exec.assert_called_once()
    stmt = session.exec.call_args.args[0]
    assert getattr(stmt, "_for_update_arg", None) is not None
    session.flush.assert_called_once()
    assert isinstance(pago, PagoCxC)
