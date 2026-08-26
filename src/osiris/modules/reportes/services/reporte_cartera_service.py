from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlmodel import Session, select

from osiris.core.company_scope import resolve_company_scope
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.compras.models import Compra, CuentaPorPagar
from osiris.modules.sri.core_sri.schemas import q2
from osiris.modules.sri.core_sri.types import EstadoCuentaPorCobrar, EstadoCuentaPorPagar
from osiris.modules.reportes.schemas import (
    ReporteCarteraCobrarItemRead,
    ReporteCarteraPagarItemRead,
)
from osiris.modules.ventas.models import CuentaPorCobrar, Venta


class ReporteCarteraService:
    @staticmethod
    def _empresa_scope() -> UUID | None:
        return resolve_company_scope()

    @staticmethod
    def _d(value: object, default: str = "0.00") -> Decimal:
        if value is None:
            return Decimal(default)
        return Decimal(str(value))

    def obtener_cartera_cobrar(self, session: Session) -> list[ReporteCarteraCobrarItemRead]:
        empresa_scope = self._empresa_scope()
        stmt = (
            select(
                Venta.cliente_id,
                func.coalesce(func.sum(CuentaPorCobrar.saldo_pendiente), 0).label("saldo"),
            )
            .select_from(CuentaPorCobrar)
            .join(Venta, Venta.id == CuentaPorCobrar.venta_id)
            .where(
                CuentaPorCobrar.activo.is_(True),
                Venta.activo.is_(True),
                CuentaPorCobrar.saldo_pendiente > Decimal("0"),
                CuentaPorCobrar.estado.in_(
                    [EstadoCuentaPorCobrar.PENDIENTE, EstadoCuentaPorCobrar.PARCIAL]
                ),
                Venta.cliente_id.is_not(None),
            )
            .group_by(Venta.cliente_id)
            .order_by(func.sum(CuentaPorCobrar.saldo_pendiente).desc())
        )
        if empresa_scope is not None:
            stmt = stmt.where(Venta.empresa_id == empresa_scope)
        rows = session.exec(stmt).all()
        return [
            ReporteCarteraCobrarItemRead(
                cliente_id=cliente_id,
                saldo_pendiente=q2(self._d(saldo)),
            )
            for cliente_id, saldo in rows
        ]

    def obtener_cartera_pagar(self, session: Session) -> list[ReporteCarteraPagarItemRead]:
        empresa_scope = self._empresa_scope()
        stmt = (
            select(
                Compra.proveedor_id,
                func.coalesce(func.sum(CuentaPorPagar.saldo_pendiente), 0).label("saldo"),
            )
            .select_from(CuentaPorPagar)
            .join(Compra, Compra.id == CuentaPorPagar.compra_id)
            .where(
                CuentaPorPagar.activo.is_(True),
                Compra.activo.is_(True),
                CuentaPorPagar.saldo_pendiente > Decimal("0"),
                CuentaPorPagar.estado.in_(
                    [EstadoCuentaPorPagar.PENDIENTE, EstadoCuentaPorPagar.PARCIAL]
                ),
            )
            .group_by(Compra.proveedor_id)
            .order_by(func.sum(CuentaPorPagar.saldo_pendiente).desc())
        )
        if empresa_scope is not None:
            stmt = stmt.join(Sucursal, Sucursal.id == Compra.sucursal_id).where(
                Sucursal.activo.is_(True),
                Sucursal.empresa_id == empresa_scope,
            )
        rows = session.exec(stmt).all()
        return [
            ReporteCarteraPagarItemRead(
                proveedor_id=proveedor_id,
                saldo_pendiente=q2(self._d(saldo)),
            )
            for proveedor_id, saldo in rows
        ]
