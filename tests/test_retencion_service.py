from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from osiris.modules.sri.core_sri.models import (
    Compra,
    EstadoCompra,
    FormaPagoSRI,
    PlantillaRetencion,
    PlantillaRetencionDetalle,
    SustentoTributarioSRI,
    TipoIdentificacionSRI,
    TipoRetencionSRI,
)
from osiris.modules.compras.services.retencion_service import RetencionService


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
            PlantillaRetencion.__table__,
            PlantillaRetencionDetalle.__table__,
        ],
    )
    return engine


def test_sugerir_retencion_aplica_bases_correctas():
    engine = _build_test_engine()
    service = RetencionService()

    with Session(engine) as session:
        proveedor_id = uuid4()
        compra = Compra(
            proveedor_id=proveedor_id,
            secuencial_factura="001-001-123456789",
            autorizacion_sri="1" * 49,
            fecha_emision=date.today(),
            sustento_tributario=SustentoTributarioSRI.CREDITO_TRIBUTARIO_BIENES,
            tipo_identificacion_proveedor=TipoIdentificacionSRI.RUC,
            identificacion_proveedor="1790012345001",
            forma_pago=FormaPagoSRI.TRANSFERENCIA,
            subtotal_sin_impuestos=Decimal("100.00"),
            subtotal_12=Decimal("100.00"),
            subtotal_15=Decimal("0.00"),
            subtotal_0=Decimal("0.00"),
            subtotal_no_objeto=Decimal("0.00"),
            monto_iva=Decimal("12.00"),
            monto_ice=Decimal("0.00"),
            valor_total=Decimal("112.00"),
            estado=EstadoCompra.REGISTRADA,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(compra)
        session.flush()

        plantilla = PlantillaRetencion(
            proveedor_id=proveedor_id,
            nombre="Plantilla proveedor",
            es_global=False,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(plantilla)
        session.flush()

        session.add(
            PlantillaRetencionDetalle(
                plantilla_retencion_id=plantilla.id,
                codigo_retencion_sri="312",
                tipo=TipoRetencionSRI.IVA,
                porcentaje=Decimal("30.00"),
                usuario_auditoria="seed",
                activo=True,
            )
        )
        session.add(
            PlantillaRetencionDetalle(
                plantilla_retencion_id=plantilla.id,
                codigo_retencion_sri="303",
                tipo=TipoRetencionSRI.RENTA,
                porcentaje=Decimal("1.00"),
                usuario_auditoria="seed",
                activo=True,
            )
        )
        session.commit()

        sugerencia = service.sugerir_retencion(session, compra.id)
        assert len(sugerencia.detalles) == 2

        det_iva = next(d for d in sugerencia.detalles if d.tipo == TipoRetencionSRI.IVA)
        det_renta = next(d for d in sugerencia.detalles if d.tipo == TipoRetencionSRI.RENTA)

        assert det_iva.base_calculo == Decimal("12.00")
        assert det_iva.valor_retenido == Decimal("3.60")
        assert det_renta.base_calculo == Decimal("100.00")
        assert det_renta.valor_retenido == Decimal("1.00")
        assert sugerencia.total_retenido == Decimal("4.60")
