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
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.punto_emision.entity import PuntoEmision
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.compras.models import Compra, Retencion, RetencionDetalle
from osiris.modules.sri.core_sri.types import (
    EstadoCompra,
    EstadoRetencion,
    EstadoRetencionRecibida,
    EstadoVenta,
    FormaPagoSRI,
    SustentoTributarioSRI,
    TipoIdentificacionSRI,
    TipoRetencionSRI,
)
from osiris.modules.ventas.models import RetencionRecibida, RetencionRecibidaDetalle, Venta
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
            PuntoEmision.__table__,
            Venta.__table__,
            Compra.__table__,
            Retencion.__table__,
            RetencionDetalle.__table__,
            RetencionRecibida.__table__,
            RetencionRecibidaDetalle.__table__,
        ],
    )
    return engine


def _compra(
    *,
    fecha_emision: date,
    subtotal_0: str,
    subtotal_12: str,
    subtotal_15: str = "0.00",
    monto_iva: str,
    total: str,
    estado: EstadoCompra = EstadoCompra.REGISTRADA,
) -> Compra:
    return Compra(
        proveedor_id=uuid4(),
        secuencial_factura=f"001-001-{str(uuid4().int)[-9:]}",
        autorizacion_sri=str(uuid4().int)[:37],
        fecha_emision=fecha_emision,
        sustento_tributario=SustentoTributarioSRI.CREDITO_TRIBUTARIO_BIENES,
        tipo_identificacion_proveedor=TipoIdentificacionSRI.RUC,
        identificacion_proveedor=f"{str(uuid4().int)[:13]}",
        forma_pago=FormaPagoSRI.TRANSFERENCIA,
        subtotal_sin_impuestos=Decimal(subtotal_0) + Decimal(subtotal_12) + Decimal(subtotal_15),
        subtotal_12=Decimal(subtotal_12),
        subtotal_15=Decimal(subtotal_15),
        subtotal_0=Decimal(subtotal_0),
        subtotal_no_objeto=Decimal("0.00"),
        monto_iva=Decimal(monto_iva),
        monto_ice=Decimal("0.00"),
        valor_total=Decimal(total),
        estado=estado,
        usuario_auditoria="test",
        activo=True,
    )


def _venta(
    *,
    fecha_emision: date,
    subtotal_0: str,
    subtotal_12: str,
    subtotal_15: str = "0.00",
    monto_iva: str,
    total: str,
    estado: EstadoVenta = EstadoVenta.EMITIDA,
) -> Venta:
    return Venta(
        fecha_emision=fecha_emision,
        tipo_identificacion_comprador=TipoIdentificacionSRI.RUC,
        identificacion_comprador=f"{str(uuid4().int)[:13]}",
        forma_pago=FormaPagoSRI.EFECTIVO,
        subtotal_sin_impuestos=Decimal(subtotal_0) + Decimal(subtotal_12) + Decimal(subtotal_15),
        subtotal_12=Decimal(subtotal_12),
        subtotal_15=Decimal(subtotal_15),
        subtotal_0=Decimal(subtotal_0),
        subtotal_no_objeto=Decimal("0.00"),
        monto_iva=Decimal(monto_iva),
        monto_ice=Decimal("0.00"),
        valor_total=Decimal(total),
        estado=estado,
        usuario_auditoria="test",
        activo=True,
    )


def test_reporte_mensual_104_completo():
    engine = _build_test_engine()
    with Session(engine) as session:
        # Ventas del mes (incluye una anulada para exclusión)
        venta_ok = _venta(
            fecha_emision=date(2026, 2, 12),
            subtotal_0="100.00",
            subtotal_12="500.00",
            monto_iva="75.00",
            total="675.00",
        )
        session.add(venta_ok)
        session.add(
            _venta(
                fecha_emision=date(2026, 2, 13),
                subtotal_0="999.00",
                subtotal_12="0.00",
                monto_iva="0.00",
                total="999.00",
                estado=EstadoVenta.ANULADA,
            )
        )
        session.add(
            _venta(
                fecha_emision=date(2026, 3, 2),
                subtotal_0="50.00",
                subtotal_12="0.00",
                monto_iva="0.00",
                total="50.00",
            )
        )
        session.flush()

        # Compras del mes (incluye anulada y fuera de mes)
        compra_ok = _compra(
            fecha_emision=date(2026, 2, 10),
            subtotal_0="50.00",
            subtotal_12="20.00",
            monto_iva="2.40",
            total="72.40",
        )
        session.add(compra_ok)
        session.flush()

        session.add(
            _compra(
                fecha_emision=date(2026, 2, 11),
                subtotal_0="999.00",
                subtotal_12="0.00",
                monto_iva="0.00",
                total="999.00",
                estado=EstadoCompra.ANULADA,
            )
        )
        session.add(
            _compra(
                fecha_emision=date(2026, 3, 1),
                subtotal_0="10.00",
                subtotal_12="0.00",
                monto_iva="0.00",
                total="10.00",
            )
        )
        session.flush()

        # Retenciones emitidas (pasivo)
        ret_emit_ok = Retencion(
            compra_id=compra_ok.id,
            fecha_emision=date(2026, 2, 10),
            estado=EstadoRetencion.EMITIDA,
            total_retenido=Decimal("7.00"),
            usuario_auditoria="test",
            activo=True,
        )
        session.add(ret_emit_ok)
        session.flush()
        session.add(
            RetencionDetalle(
                retencion_id=ret_emit_ok.id,
                codigo_retencion_sri="312",
                tipo=TipoRetencionSRI.RENTA,
                porcentaje=Decimal("1.00"),
                base_calculo=Decimal("50.00"),
                valor_retenido=Decimal("5.00"),
                usuario_auditoria="test",
                activo=True,
            )
        )
        session.add(
            RetencionDetalle(
                retencion_id=ret_emit_ok.id,
                codigo_retencion_sri="441",
                tipo=TipoRetencionSRI.IVA,
                porcentaje=Decimal("10.00"),
                base_calculo=Decimal("20.00"),
                valor_retenido=Decimal("2.00"),
                usuario_auditoria="test",
                activo=True,
            )
        )

        # Retenciones recibidas (crédito)
        ret_rec_ok = RetencionRecibida(
            venta_id=venta_ok.id,
            cliente_id=uuid4(),
            numero_retencion="001-001-000000123",
            fecha_emision=date(2026, 2, 12),
            estado=EstadoRetencionRecibida.APLICADA,
            total_retenido=Decimal("5.50"),
            usuario_auditoria="test",
            activo=True,
        )
        session.add(ret_rec_ok)
        session.flush()
        session.add(
            RetencionRecibidaDetalle(
                retencion_recibida_id=ret_rec_ok.id,
                codigo_impuesto_sri="1",
                porcentaje_aplicado=Decimal("1.00"),
                base_imponible=Decimal("100.00"),
                valor_retenido=Decimal("3.00"),
                usuario_auditoria="test",
                activo=True,
            )
        )
        session.add(
            RetencionRecibidaDetalle(
                retencion_recibida_id=ret_rec_ok.id,
                codigo_impuesto_sri="2",
                porcentaje_aplicado=Decimal("10.00"),
                base_imponible=Decimal("25.00"),
                valor_retenido=Decimal("2.50"),
                usuario_auditoria="test",
                activo=True,
            )
        )
        # Excluida por estado no aplicada
        ret_rec_borrador = RetencionRecibida(
            venta_id=venta_ok.id,
            cliente_id=uuid4(),
            numero_retencion="001-001-000000124",
            fecha_emision=date(2026, 2, 14),
            estado=EstadoRetencionRecibida.BORRADOR,
            total_retenido=Decimal("99.00"),
            usuario_auditoria="test",
            activo=True,
        )
        session.add(ret_rec_borrador)
        session.flush()
        session.add(
            RetencionRecibidaDetalle(
                retencion_recibida_id=ret_rec_borrador.id,
                codigo_impuesto_sri="1",
                porcentaje_aplicado=Decimal("1.00"),
                base_imponible=Decimal("99.00"),
                valor_retenido=Decimal("99.00"),
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
            response = client.get(
                "/api/v1/reportes/impuestos/mensual",
                params={"mes": 2, "anio": 2026},
            )
        assert response.status_code == 200, response.text
        data = response.json()

        assert Decimal(str(data["ventas"]["base_0"])) == Decimal("100.00")
        assert Decimal(str(data["ventas"]["base_iva"])) == Decimal("500.00")
        assert Decimal(str(data["ventas"]["monto_iva"])) == Decimal("75.00")
        assert Decimal(str(data["ventas"]["total"])) == Decimal("675.00")
        assert int(data["ventas"]["total_documentos"]) == 1

        assert Decimal(str(data["compras"]["base_0"])) == Decimal("50.00")
        assert Decimal(str(data["compras"]["base_iva"])) == Decimal("20.00")
        assert Decimal(str(data["compras"]["monto_iva"])) == Decimal("2.40")
        assert Decimal(str(data["compras"]["total"])) == Decimal("72.40")
        assert int(data["compras"]["total_documentos"]) == 1

        assert Decimal(str(data["retenciones_emitidas"]["1"])) == Decimal("5.00")
        assert Decimal(str(data["retenciones_emitidas"]["2"])) == Decimal("2.00")

        assert Decimal(str(data["retenciones_recibidas"]["1"])) == Decimal("3.00")
        assert Decimal(str(data["retenciones_recibidas"]["2"])) == Decimal("2.50")
    finally:
        app.dependency_overrides.pop(get_session, None)
