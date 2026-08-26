from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlmodel import Session, select

from osiris.core.company_scope import resolve_company_scope
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.common.proveedor_sociedad.entity import ProveedorSociedad
from osiris.modules.compras.models import Compra
from osiris.modules.sri.core_sri.schemas import q2
from osiris.modules.sri.core_sri.types import EstadoCompra
from osiris.modules.reportes.schemas import ReporteComprasPorProveedorRead


class ReporteComprasService:
    @staticmethod
    def _empresa_scope() -> UUID | None:
        return resolve_company_scope()

    @staticmethod
    def _d(value: object, default: str = "0.00") -> Decimal:
        if value is None:
            return Decimal(default)
        return Decimal(str(value))

    def obtener_compras_por_proveedor(
        self,
        session: Session,
        *,
        fecha_inicio: date,
        fecha_fin: date,
        sucursal_id: UUID | None = None,
    ) -> list[ReporteComprasPorProveedorRead]:
        empresa_scope = self._empresa_scope()
        filtros = [
            Compra.activo.is_(True),
            Compra.estado != EstadoCompra.ANULADA,
            Compra.fecha_emision >= fecha_inicio,
            Compra.fecha_emision <= fecha_fin,
        ]
        if sucursal_id is not None:
            filtros.append(Compra.sucursal_id == sucursal_id)

        razon_social_expr = func.coalesce(
            ProveedorSociedad.razon_social,
            Compra.identificacion_proveedor,
            "SIN_RAZON_SOCIAL",
        )
        total_expr = func.coalesce(func.sum(Compra.valor_total), 0)
        facturas_expr = func.count(Compra.id)

        stmt = (
            select(
                Compra.proveedor_id,
                razon_social_expr.label("razon_social"),
                total_expr.label("total_compras"),
                facturas_expr.label("cantidad_facturas"),
            )
            .select_from(Compra)
            .outerjoin(ProveedorSociedad, ProveedorSociedad.id == Compra.proveedor_id)
            .where(*filtros)
            .group_by(Compra.proveedor_id, razon_social_expr)
            .order_by(total_expr.desc(), razon_social_expr.asc())
        )
        if empresa_scope is not None:
            stmt = stmt.join(Sucursal, Sucursal.id == Compra.sucursal_id).where(
                Sucursal.activo.is_(True),
                Sucursal.empresa_id == empresa_scope,
            )

        rows = session.exec(stmt).all()
        return [
            ReporteComprasPorProveedorRead(
                proveedor_id=proveedor_id,
                razon_social=str(razon_social),
                total_compras=q2(self._d(total_compras)),
                cantidad_facturas=int(cantidad_facturas or 0),
            )
            for proveedor_id, razon_social, total_compras, cantidad_facturas in rows
        ]
