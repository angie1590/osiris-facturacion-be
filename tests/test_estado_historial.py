from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.sri.core_sri.models import (
    Compra,
    CompraEstadoHistorial,
    DocumentoElectronico,
    DocumentoElectronicoHistorial,
    EstadoCompra,
    EstadoDocumentoElectronico,
    FormaPagoSRI,
    TipoIdentificacionSRI,
    Venta,
    VentaEstadoHistorial,
)
from osiris.modules.sri.facturacion_electronica.services.estado_historial_service import EstadoHistorialService
from osiris.modules.sri.facturacion_electronica.services.fe_mapper_service import FEMapperService


def _build_test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(
        engine,
        tables=[
            Venta.__table__,
            Compra.__table__,
            DocumentoElectronico.__table__,
            VentaEstadoHistorial.__table__,
            CompraEstadoHistorial.__table__,
            DocumentoElectronicoHistorial.__table__,
            AuditLog.__table__,
        ],
    )
    return engine


def _venta_base() -> Venta:
    return Venta(
        fecha_emision=date.today(),
        tipo_identificacion_comprador=TipoIdentificacionSRI.RUC,
        identificacion_comprador="1790012345001",
        forma_pago=FormaPagoSRI.EFECTIVO,
        subtotal_sin_impuestos=Decimal("100.00"),
        subtotal_12=Decimal("0.00"),
        subtotal_15=Decimal("0.00"),
        subtotal_0=Decimal("100.00"),
        subtotal_no_objeto=Decimal("0.00"),
        monto_iva=Decimal("0.00"),
        monto_ice=Decimal("0.00"),
        valor_total=Decimal("100.00"),
        usuario_auditoria="tester",
        activo=True,
    )


def _compra_base() -> Compra:
    return Compra(
        proveedor_id=uuid4(),
        secuencial_factura="001-001-123456789",
        autorizacion_sri="1" * 49,
        fecha_emision=date.today(),
        sustento_tributario="01",
        tipo_identificacion_proveedor=TipoIdentificacionSRI.RUC,
        identificacion_proveedor="1790099988001",
        forma_pago=FormaPagoSRI.TRANSFERENCIA,
        subtotal_sin_impuestos=Decimal("50.00"),
        subtotal_12=Decimal("0.00"),
        subtotal_15=Decimal("0.00"),
        subtotal_0=Decimal("50.00"),
        subtotal_no_objeto=Decimal("0.00"),
        monto_iva=Decimal("0.00"),
        monto_ice=Decimal("0.00"),
        valor_total=Decimal("50.00"),
        usuario_auditoria="tester",
        activo=True,
    )


def test_state_transition_logging():
    engine = _build_test_engine()
    service = EstadoHistorialService()

    with Session(engine) as session:
        compra = _compra_base()
        session.add(compra)
        session.commit()
        session.refresh(compra)

        service.actualizar_estado_compra(
            session,
            compra.id,
            EstadoCompra.PAGADA,
            usuario_id="usuario-pagos",
            motivo_cambio="Pago total de orden de compra",
        )

        session.refresh(compra)
        historial = session.exec(
            select(CompraEstadoHistorial).where(CompraEstadoHistorial.entidad_id == compra.id)
        ).one()

        assert compra.estado == EstadoCompra.PAGADA
        assert historial.estado_anterior == EstadoCompra.PENDIENTE.value
        assert historial.estado_nuevo == EstadoCompra.PAGADA.value
        assert historial.usuario_id == "usuario-pagos"


def test_mandatory_reason_on_anulation():
    engine = _build_test_engine()
    service = EstadoHistorialService()

    with Session(engine) as session:
        venta = _venta_base()
        session.add(venta)
        session.commit()
        session.refresh(venta)

        with pytest.raises(ValueError, match="motivo_cambio es obligatorio"):
            service.anular_venta(
                session,
                venta.id,
                usuario_id="usuario-conta",
                motivo_cambio="   ",
            )

        registros = session.exec(select(VentaEstadoHistorial)).all()
        assert registros == []


def test_sri_rejection_logging():
    engine = _build_test_engine()
    mapper = FEMapperService()

    with Session(engine) as session:
        venta = _venta_base()
        session.add(venta)
        session.commit()
        session.refresh(venta)

        documento = DocumentoElectronico(
            venta_id=venta.id,
            clave_acceso="1" * 49,
            estado=EstadoDocumentoElectronico.ENVIADO,
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(documento)
        session.commit()
        session.refresh(documento)

        mapper.registrar_respuesta_sri(
            session,
            documento.id,
            EstadoDocumentoElectronico.RECHAZADO,
            mensaje_sri="Clave de acceso duplicada",
            usuario_id="sri-bot",
        )

        session.refresh(documento)
        historial = session.exec(
            select(DocumentoElectronicoHistorial).where(
                DocumentoElectronicoHistorial.entidad_id == documento.id
            )
        ).one()

        assert documento.estado == EstadoDocumentoElectronico.RECHAZADO
        assert historial.estado_anterior == EstadoDocumentoElectronico.ENVIADO.value
        assert historial.estado_nuevo == EstadoDocumentoElectronico.RECHAZADO.value
        assert historial.motivo_cambio == "Clave de acceso duplicada"
