from __future__ import annotations

from datetime import date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import func
from sqlmodel import Session, select

from osiris.core.company_scope import resolve_company_scope
from osiris.modules.common.punto_emision.entity import PuntoEmision
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.compras.models import Compra, Retencion
from osiris.modules.sri.core_sri.types import TipoDocumentoElectronico
from osiris.modules.sri.facturacion_electronica.models import DocumentoElectronico
from osiris.modules.reportes.schemas import ReporteMonitorSRIEstadoRead
from osiris.modules.ventas.models import Venta


class ReporteMonitorSRIService:
    @staticmethod
    def _empresa_scope() -> UUID | None:
        return resolve_company_scope()

    @staticmethod
    def _rango_fechas(fecha_inicio: date, fecha_fin: date) -> tuple[datetime, datetime]:
        dt_inicio = datetime.combine(fecha_inicio, time.min)
        dt_fin_exclusivo = datetime.combine(fecha_fin + timedelta(days=1), time.min)
        return dt_inicio, dt_fin_exclusivo

    def obtener_monitor_estados(
        self,
        session: Session,
        *,
        fecha_inicio: date,
        fecha_fin: date,
        sucursal_id: UUID | None = None,
    ) -> list[ReporteMonitorSRIEstadoRead]:
        empresa_scope = self._empresa_scope()
        dt_inicio, dt_fin_exclusivo = self._rango_fechas(fecha_inicio, fecha_fin)

        filtros_base = [
            DocumentoElectronico.activo.is_(True),
            DocumentoElectronico.creado_en >= dt_inicio,
            DocumentoElectronico.creado_en < dt_fin_exclusivo,
        ]

        total_expr = func.count(DocumentoElectronico.id)

        stmt_facturas = (
            select(
                DocumentoElectronico.estado_sri,
                DocumentoElectronico.tipo_documento,
                total_expr.label("cantidad"),
            )
            .select_from(DocumentoElectronico)
            .where(
                *filtros_base,
                DocumentoElectronico.tipo_documento == TipoDocumentoElectronico.FACTURA,
            )
        )
        if sucursal_id is not None or empresa_scope is not None:
            stmt_facturas = (
                stmt_facturas.join(Venta, Venta.id == DocumentoElectronico.venta_id)
            )
            if empresa_scope is not None:
                stmt_facturas = stmt_facturas.where(Venta.empresa_id == empresa_scope)
            if sucursal_id is not None:
                stmt_facturas = (
                    stmt_facturas
                    .join(PuntoEmision, PuntoEmision.id == Venta.punto_emision_id)
                    .where(PuntoEmision.sucursal_id == sucursal_id)
                )
        stmt_facturas = stmt_facturas.group_by(
            DocumentoElectronico.estado_sri,
            DocumentoElectronico.tipo_documento,
        )

        stmt_retenciones = (
            select(
                DocumentoElectronico.estado_sri,
                DocumentoElectronico.tipo_documento,
                total_expr.label("cantidad"),
            )
            .select_from(DocumentoElectronico)
            .where(
                *filtros_base,
                DocumentoElectronico.tipo_documento == TipoDocumentoElectronico.RETENCION,
            )
        )
        if sucursal_id is not None or empresa_scope is not None:
            stmt_retenciones = (
                stmt_retenciones.join(Retencion, Retencion.id == DocumentoElectronico.referencia_id)
                .join(Compra, Compra.id == Retencion.compra_id)
            )
            if empresa_scope is not None:
                stmt_retenciones = stmt_retenciones.join(Sucursal, Sucursal.id == Compra.sucursal_id).where(
                    Sucursal.activo.is_(True),
                    Sucursal.empresa_id == empresa_scope,
                )
            if sucursal_id is not None:
                stmt_retenciones = stmt_retenciones.where(Compra.sucursal_id == sucursal_id)
        stmt_retenciones = stmt_retenciones.group_by(
            DocumentoElectronico.estado_sri,
            DocumentoElectronico.tipo_documento,
        )

        rows = list(session.exec(stmt_facturas).all()) + list(session.exec(stmt_retenciones).all())
        return [
            ReporteMonitorSRIEstadoRead(
                estado=getattr(estado, "value", str(estado)),
                tipo_documento=getattr(tipo_documento, "value", str(tipo_documento)),
                cantidad=int(cantidad or 0),
            )
            for estado, tipo_documento, cantidad in rows
        ]
