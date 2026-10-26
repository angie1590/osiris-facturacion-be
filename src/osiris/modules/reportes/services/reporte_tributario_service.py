from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, func, select as sa_select
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement, Label
from sqlalchemy.sql.expression import SQLColumnExpression
from sqlmodel import Session, col, select

from osiris.core.company_scope import resolve_company_scope
from osiris.modules.common.punto_emision.entity import PuntoEmision
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.compras.models import Compra, Retencion, RetencionDetalle
from osiris.modules.sri.core_sri.types import (
    EstadoCompra,
    EstadoRetencion,
    EstadoRetencionRecibida,
    EstadoVenta,
    TipoRetencionSRI,
)
from osiris.modules.reportes.schemas import (
    ReportePre104BloqueRead,
    ReporteImpuestosMensualRead,
)
from osiris.modules.ventas.models import (
    RetencionRecibida,
    RetencionRecibidaDetalle,
    Venta,
)
from osiris.modules.sri.core_sri.schemas import q2


class ReporteTributarioService:
    @staticmethod
    def _empresa_scope() -> UUID | None:
        return resolve_company_scope()

    @staticmethod
    def _d(value: object, default: str = "0.00") -> Decimal:
        if value is None:
            return Decimal(default)
        return Decimal(str(value))

    @staticmethod
    def _period_filters(
        session: Session, field: SQLColumnExpression[date], mes: int, anio: int
    ) -> list[ColumnElement[bool]]:
        bind = session.get_bind()
        dialect = bind.dialect.name if bind is not None else ""
        if dialect == "postgresql":
            return [
                func.extract("month", field) == mes,
                func.extract("year", field) == anio,
            ]
        return [
            func.strftime("%m", field) == f"{mes:02d}",
            func.strftime("%Y", field) == str(anio),
        ]

    def obtener_reporte_mensual_impuestos(
        self,
        session: Session,
        *,
        mes: int,
        anio: int,
        sucursal_id: UUID | None = None,
    ) -> ReporteImpuestosMensualRead:
        empresa_scope = self._empresa_scope()
        ventas_filtros = [
            col(Venta.activo).is_(True),
            col(Venta.estado) != EstadoVenta.ANULADA,
            *self._period_filters(session, col(Venta.fecha_emision), mes, anio),
        ]
        if empresa_scope is not None:
            ventas_filtros.append(col(Venta.empresa_id) == empresa_scope)
        if sucursal_id is not None:
            ventas_filtros.append(col(PuntoEmision.sucursal_id) == sucursal_id)

        ventas_stmt = sa_select(
            func.coalesce(func.sum(col(Venta.subtotal_0)), 0),
            func.coalesce(func.sum(col(Venta.subtotal_12)), 0),
            func.coalesce(func.sum(col(Venta.subtotal_15)), 0),
            func.coalesce(func.sum(col(Venta.monto_iva)), 0),
            func.coalesce(func.sum(col(Venta.valor_total)), 0),
            func.count(col(Venta.id)),
        ).select_from(Venta)
        if sucursal_id is not None:
            ventas_stmt = ventas_stmt.join(
                PuntoEmision, col(PuntoEmision.id) == col(Venta.punto_emision_id)
            )
        ventas_stmt = ventas_stmt.where(*ventas_filtros)
        (
            ventas_subtotal_0,
            ventas_subtotal_12,
            ventas_subtotal_15,
            ventas_monto_iva,
            ventas_total,
            ventas_count,
        ) = session.execute(ventas_stmt).one()
        ventas = ReportePre104BloqueRead(
            base_0=q2(self._d(ventas_subtotal_0)),
            base_iva=q2(self._d(ventas_subtotal_12) + self._d(ventas_subtotal_15)),
            monto_iva=q2(self._d(ventas_monto_iva)),
            total=q2(self._d(ventas_total)),
            total_documentos=int(ventas_count or 0),
        )

        compras_filtros = [
            col(Compra.activo).is_(True),
            col(Compra.estado) != EstadoCompra.ANULADA,
            *self._period_filters(session, col(Compra.fecha_emision), mes, anio),
        ]
        if sucursal_id is not None:
            compras_filtros.append(col(Compra.sucursal_id) == sucursal_id)

        compras_stmt = sa_select(
            func.coalesce(func.sum(col(Compra.subtotal_0)), 0),
            func.coalesce(func.sum(col(Compra.subtotal_12)), 0),
            func.coalesce(func.sum(col(Compra.subtotal_15)), 0),
            func.coalesce(func.sum(col(Compra.monto_iva)), 0),
            func.coalesce(func.sum(col(Compra.valor_total)), 0),
            func.count(col(Compra.id)),
        )
        if empresa_scope is not None:
            compras_stmt = compras_stmt.join(
                Sucursal, col(Sucursal.id) == col(Compra.sucursal_id)
            ).where(
                col(Sucursal.activo).is_(True),
                col(Sucursal.empresa_id) == empresa_scope,
            )
        compras_stmt = compras_stmt.where(*compras_filtros)
        (
            subtotal_0,
            subtotal_12,
            subtotal_15,
            monto_iva,
            total,
            total_documentos,
        ) = session.execute(compras_stmt).one()

        compras = ReportePre104BloqueRead(
            base_0=q2(self._d(subtotal_0)),
            base_iva=q2(self._d(subtotal_12) + self._d(subtotal_15)),
            monto_iva=q2(self._d(monto_iva)),
            total=q2(self._d(total)),
            total_documentos=int(total_documentos or 0),
        )

        codigo_pasivo_expr = case(
            (col(RetencionDetalle.tipo) == TipoRetencionSRI.RENTA, "1"),
            (col(RetencionDetalle.tipo) == TipoRetencionSRI.IVA, "2"),
            else_=col(RetencionDetalle.codigo_retencion_sri),
        )
        pasivo_stmt = (
            select(
                codigo_pasivo_expr.label("codigo_sri"),
                func.coalesce(func.sum(col(RetencionDetalle.valor_retenido)), 0).label(
                    "total"
                ),
            )
            .select_from(RetencionDetalle)
            .join(Retencion, col(Retencion.id) == col(RetencionDetalle.retencion_id))
            .join(Compra, col(Compra.id) == col(Retencion.compra_id))
            .where(
                col(RetencionDetalle.activo).is_(True),
                col(Retencion.activo).is_(True),
                col(Compra.activo).is_(True),
                col(Retencion.estado) == EstadoRetencion.EMITIDA,
                col(Compra.estado) != EstadoCompra.ANULADA,
                *self._period_filters(session, col(Compra.fecha_emision), mes, anio),
            )
            .group_by(codigo_pasivo_expr)
            .order_by(codigo_pasivo_expr.asc())
        )
        if empresa_scope is not None:
            pasivo_stmt = pasivo_stmt.join(
                Sucursal, col(Sucursal.id) == col(Compra.sucursal_id)
            ).where(
                col(Sucursal.activo).is_(True),
                col(Sucursal.empresa_id) == empresa_scope,
            )
        if sucursal_id is not None:
            pasivo_stmt = pasivo_stmt.where(col(Compra.sucursal_id) == sucursal_id)
        pasivo_rows = session.exec(pasivo_stmt).all()
        pasivo = {
            str(codigo_sri): q2(self._d(total_retenido))
            for codigo_sri, total_retenido in pasivo_rows
        }

        codigo_credito_expr: Label[str] = col(
            RetencionRecibidaDetalle.codigo_impuesto_sri
        ).label("codigo_sri")
        credito_stmt: Select[tuple[str, Decimal]] = (
            sa_select(
                codigo_credito_expr,
                func.coalesce(
                    func.sum(col(RetencionRecibidaDetalle.valor_retenido)), 0
                ).label("total"),
            )
            .select_from(RetencionRecibidaDetalle)
            .join(
                RetencionRecibida,
                col(RetencionRecibida.id)
                == col(RetencionRecibidaDetalle.retencion_recibida_id),
            )
            .join(Venta, col(Venta.id) == col(RetencionRecibida.venta_id))
            .where(
                col(RetencionRecibidaDetalle.activo).is_(True),
                col(RetencionRecibida.activo).is_(True),
                col(RetencionRecibida.estado) == EstadoRetencionRecibida.APLICADA,
                *self._period_filters(
                    session, col(RetencionRecibida.fecha_emision), mes, anio
                ),
            )
            .group_by(col(RetencionRecibidaDetalle.codigo_impuesto_sri))
            .order_by(col(RetencionRecibidaDetalle.codigo_impuesto_sri).asc())
        )
        if empresa_scope is not None:
            credito_stmt = credito_stmt.where(col(Venta.empresa_id) == empresa_scope)
        if sucursal_id is not None:
            credito_stmt = credito_stmt.join(
                PuntoEmision, col(PuntoEmision.id) == col(Venta.punto_emision_id)
            ).where(col(PuntoEmision.sucursal_id) == sucursal_id)
        credito_rows = session.execute(credito_stmt).all()
        credito = {
            str(codigo_sri): q2(self._d(total_retenido))
            for codigo_sri, total_retenido in credito_rows
        }

        return ReporteImpuestosMensualRead(
            mes=mes,
            anio=anio,
            sucursal_id=sucursal_id,
            ventas=ventas,
            compras=compras,
            retenciones_emitidas=pasivo,
            retenciones_recibidas=credito,
        )
