from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from osiris.modules.compras.services.cxp_service import CuentaPorPagarService
from osiris.modules.sri.core_sri.models import (
    Compra,
    CuentaPorPagar,
    EstadoCompra,
    EstadoCuentaPorPagar,
    FormaPagoSRI,
    PagoCxP,
    SustentoTributarioSRI,
    TipoIdentificacionSRI,
)
from osiris.modules.sri.core_sri.all_schemas import PagoCxPCreate


def _build_test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(
        engine,
        tables=[
            Compra.__table__,
            CuentaPorPagar.__table__,
            PagoCxP.__table__,
        ],
    )
    return engine


def _crear_cxp(
    session: Session,
    *,
    valor_total: Decimal,
    valor_retenido: Decimal,
    saldo_pendiente: Decimal,
    estado: EstadoCuentaPorPagar = EstadoCuentaPorPagar.PENDIENTE,
) -> CuentaPorPagar:
    compra = Compra(
        proveedor_id=uuid4(),
        secuencial_factura="001-001-123456789",
        autorizacion_sri="1" * 49,
        fecha_emision=date.today(),
        sustento_tributario=SustentoTributarioSRI.CREDITO_TRIBUTARIO_BIENES,
        tipo_identificacion_proveedor=TipoIdentificacionSRI.RUC,
        identificacion_proveedor="1790012345001",
        forma_pago=FormaPagoSRI.TRANSFERENCIA,
        subtotal_sin_impuestos=valor_total,
        subtotal_12=Decimal("0.00"),
        subtotal_15=Decimal("0.00"),
        subtotal_0=valor_total,
        subtotal_no_objeto=Decimal("0.00"),
        monto_iva=Decimal("0.00"),
        monto_ice=Decimal("0.00"),
        valor_total=valor_total,
        estado=EstadoCompra.REGISTRADA,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(compra)
    session.flush()

    cxp = CuentaPorPagar(
        compra_id=compra.id,
        valor_total_factura=valor_total,
        valor_retenido=valor_retenido,
        pagos_acumulados=Decimal("0.00"),
        saldo_pendiente=saldo_pendiente,
        estado=estado,
        usuario_auditoria="seed",
        activo=True,
    )
    session.add(cxp)
    session.commit()
    session.refresh(cxp)
    return cxp


def test_registrar_pago_cxp_actualiza_saldo_y_estado_parcial():
    engine = _build_test_engine()
    service = CuentaPorPagarService()

    with Session(engine) as session:
        cxp = _crear_cxp(
            session,
            valor_total=Decimal("100.00"),
            valor_retenido=Decimal("10.00"),
            saldo_pendiente=Decimal("90.00"),
        )

        pago = service.registrar_pago_cxp(
            session,
            cxp.id,
            PagoCxPCreate(
                monto=Decimal("40.00"),
                fecha=date.today(),
                forma_pago=FormaPagoSRI.EFECTIVO,
                usuario_auditoria="user.cxp",
            ),
        )

        assert pago.monto == Decimal("40.00")
        session.refresh(cxp)
        assert cxp.pagos_acumulados == Decimal("40.00")
        assert cxp.saldo_pendiente == Decimal("50.00")
        assert cxp.estado == EstadoCuentaPorPagar.PARCIAL

        pagos = session.exec(select(PagoCxP).where(PagoCxP.cuenta_por_pagar_id == cxp.id)).all()
        assert len(pagos) == 1


def test_pago_actualiza_saldo_y_estado():
    engine = _build_test_engine()
    service = CuentaPorPagarService()

    with Session(engine) as session:
        cxp = _crear_cxp(
            session,
            valor_total=Decimal("100.00"),
            valor_retenido=Decimal("0.00"),
            saldo_pendiente=Decimal("100.00"),
        )

        service.registrar_pago_cxp(
            session,
            cxp.id,
            PagoCxPCreate(
                monto=Decimal("40.00"),
                fecha=date.today(),
                forma_pago=FormaPagoSRI.EFECTIVO,
                usuario_auditoria="user.cxp",
            ),
        )

        session.refresh(cxp)
        assert cxp.saldo_pendiente == Decimal("60.00")
        assert cxp.estado == EstadoCuentaPorPagar.PARCIAL


def test_registrar_pago_cxp_marca_pagada_cuando_saldo_llega_cero():
    engine = _build_test_engine()
    service = CuentaPorPagarService()

    with Session(engine) as session:
        cxp = _crear_cxp(
            session,
            valor_total=Decimal("100.00"),
            valor_retenido=Decimal("0.00"),
            saldo_pendiente=Decimal("100.00"),
        )

        service.registrar_pago_cxp(
            session,
            cxp.id,
            PagoCxPCreate(
                monto=Decimal("100.00"),
                fecha=date.today(),
                forma_pago=FormaPagoSRI.TRANSFERENCIA,
                usuario_auditoria="user.cxp",
            ),
        )

        session.refresh(cxp)
        assert cxp.pagos_acumulados == Decimal("100.00")
        assert cxp.saldo_pendiente == Decimal("0.00")
        assert cxp.estado == EstadoCuentaPorPagar.PAGADA


def test_registrar_pago_cxp_rechaza_sobrepago():
    engine = _build_test_engine()
    service = CuentaPorPagarService()

    with Session(engine) as session:
        cxp = _crear_cxp(
            session,
            valor_total=Decimal("100.00"),
            valor_retenido=Decimal("0.00"),
            saldo_pendiente=Decimal("60.00"),
        )

        with pytest.raises(HTTPException) as exc:
            service.registrar_pago_cxp(
                session,
                cxp.id,
                PagoCxPCreate(
                    monto=Decimal("70.00"),
                    fecha=date.today(),
                    forma_pago=FormaPagoSRI.EFECTIVO,
                    usuario_auditoria="user.cxp",
                ),
            )
        assert exc.value.status_code == 400
        assert "no puede ser mayor al saldo pendiente" in str(exc.value.detail).lower()

        session.refresh(cxp)
        assert cxp.pagos_acumulados == Decimal("0.00")
        assert cxp.saldo_pendiente == Decimal("60.00")
        assert cxp.estado == EstadoCuentaPorPagar.PENDIENTE

        pagos = session.exec(select(PagoCxP).where(PagoCxP.cuenta_por_pagar_id == cxp.id)).all()
        assert len(pagos) == 0


def test_bloqueo_sobrepago_cxp():
    engine = _build_test_engine()
    service = CuentaPorPagarService()

    with Session(engine) as session:
        cxp = _crear_cxp(
            session,
            valor_total=Decimal("100.00"),
            valor_retenido=Decimal("0.00"),
            saldo_pendiente=Decimal("100.00"),
        )

        with pytest.raises(HTTPException) as exc:
            service.registrar_pago_cxp(
                session,
                cxp.id,
                PagoCxPCreate(
                    monto=Decimal("110.00"),
                    fecha=date.today(),
                    forma_pago=FormaPagoSRI.TRANSFERENCIA,
                    usuario_auditoria="user.cxp",
                ),
            )

        assert exc.value.status_code == 400
        assert "no puede ser mayor al saldo pendiente" in str(exc.value.detail).lower()

        session.refresh(cxp)
        assert cxp.pagos_acumulados == Decimal("0.00")
        assert cxp.saldo_pendiente == Decimal("100.00")
        assert cxp.estado == EstadoCuentaPorPagar.PENDIENTE
        pagos = session.exec(select(PagoCxP).where(PagoCxP.cuenta_por_pagar_id == cxp.id)).all()
        assert len(pagos) == 0


def test_registrar_pago_cxp_usa_bloqueo_pesimista():
    session = MagicMock()
    service = CuentaPorPagarService()

    cxp_id = uuid4()
    cxp = CuentaPorPagar(
        id=cxp_id,
        compra_id=uuid4(),
        valor_total_factura=Decimal("100.00"),
        valor_retenido=Decimal("0.00"),
        pagos_acumulados=Decimal("0.00"),
        saldo_pendiente=Decimal("100.00"),
        estado=EstadoCuentaPorPagar.PENDIENTE,
        usuario_auditoria="seed",
        activo=True,
    )
    scalar_result = MagicMock()
    compra = Compra(
        id=cxp.compra_id,
        proveedor_id=uuid4(),
        secuencial_factura="001-001-123456789",
        autorizacion_sri="1" * 49,
        fecha_emision=date.today(),
        sustento_tributario=SustentoTributarioSRI.CREDITO_TRIBUTARIO_BIENES,
        tipo_identificacion_proveedor=TipoIdentificacionSRI.RUC,
        identificacion_proveedor="1790012345001",
        forma_pago=FormaPagoSRI.TRANSFERENCIA,
        subtotal_sin_impuestos=Decimal("100.00"),
        subtotal_12=Decimal("0.00"),
        subtotal_15=Decimal("0.00"),
        subtotal_0=Decimal("100.00"),
        subtotal_no_objeto=Decimal("0.00"),
        monto_iva=Decimal("0.00"),
        monto_ice=Decimal("0.00"),
        valor_total=Decimal("100.00"),
        estado=EstadoCompra.REGISTRADA,
        usuario_auditoria="seed",
        activo=True,
    )
    scalar_result.one_or_none.return_value = (cxp, compra)
    session.exec.return_value = scalar_result

    pago = service.registrar_pago_cxp(
        session,
        cxp_id,
        PagoCxPCreate(
            monto=Decimal("20.00"),
            fecha=date.today(),
            forma_pago=FormaPagoSRI.EFECTIVO,
            usuario_auditoria="user.cxp",
        ),
        commit=False,
    )

    session.exec.assert_called_once()
    stmt = session.exec.call_args.args[0]
    assert getattr(stmt, "_for_update_arg", None) is not None
    session.flush.assert_called_once()
    assert isinstance(pago, PagoCxP)
