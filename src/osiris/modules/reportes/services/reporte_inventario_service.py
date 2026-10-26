from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import func, select as sa_select
from sqlmodel import Session, col, select

from osiris.core.company_scope import resolve_company_scope
from osiris.modules.inventario.movimientos.models import (
    EstadoMovimientoInventario,
    InventarioStock,
    MovimientoInventario,
    MovimientoInventarioDetalle,
    TipoMovimientoInventario,
)
from osiris.modules.reportes.schemas import (
    ReporteInventarioKardexMovimientoRead,
    ReporteInventarioKardexRead,
    ReporteInventarioValoracionItemRead,
    ReporteInventarioValoracionRead,
    TipoMovimientoKardex,
)
from osiris.modules.inventario.bodega.entity import Bodega
from osiris.modules.inventario.producto.entity import Producto

Q4 = Decimal("0.0001")
Q2 = Decimal("0.01")


def q4(value: Decimal | int | str) -> Decimal:
    return Decimal(str(value)).quantize(Q4, rounding=ROUND_HALF_UP)


def q2(value: Decimal | int | str) -> Decimal:
    return Decimal(str(value)).quantize(Q2, rounding=ROUND_HALF_UP)


class ReporteInventarioService:
    @staticmethod
    def _empresa_scope() -> UUID | None:
        return resolve_company_scope()

    @staticmethod
    def _d(value: object, default: str = "0") -> Decimal:
        if value is None:
            return Decimal(default)
        return Decimal(str(value))

    def obtener_valoracion_inventario(
        self, session: Session
    ) -> ReporteInventarioValoracionRead:
        empresa_scope = self._empresa_scope()
        cantidad_expr = func.coalesce(func.sum(col(InventarioStock.cantidad_actual)), 0)
        valor_expr = func.coalesce(
            func.sum(
                col(InventarioStock.cantidad_actual)
                * col(InventarioStock.costo_promedio_vigente)
            ),
            0,
        )

        stmt = (
            select(
                col(Producto.id),
                col(Producto.nombre),
                cantidad_expr.label("cantidad_actual"),
                valor_expr.label("valor_total"),
            )
            .select_from(Producto)
            .join(
                InventarioStock,
                (col(InventarioStock.producto_id) == col(Producto.id))
                & (col(InventarioStock.activo).is_(True)),
                isouter=True,
            )
            .where(col(Producto.activo).is_(True))
            .group_by(col(Producto.id), col(Producto.nombre))
            .order_by(col(Producto.nombre).asc())
        )
        if empresa_scope is not None:
            stmt = stmt.join(
                Bodega, col(Bodega.id) == col(InventarioStock.bodega_id)
            ).where(
                col(Bodega.activo).is_(True),
                col(Bodega.empresa_id) == empresa_scope,
            )

        rows = session.exec(stmt).all()

        productos: list[ReporteInventarioValoracionItemRead] = []
        patrimonio_total = Decimal("0.00")
        for producto_id, nombre, cantidad_actual, valor_total in rows:
            cantidad_d = q4(self._d(cantidad_actual))
            valor_d = q2(self._d(valor_total))
            patrimonio_total = q2(patrimonio_total + valor_d)
            costo_promedio = (
                q4(valor_d / cantidad_d)
                if cantidad_d > Decimal("0")
                else Decimal("0.0000")
            )

            productos.append(
                ReporteInventarioValoracionItemRead(
                    producto_id=producto_id,
                    nombre=nombre,
                    cantidad_actual=cantidad_d,
                    costo_promedio=costo_promedio,
                    valor_total=valor_d,
                )
            )

        return ReporteInventarioValoracionRead(
            patrimonio_total=q2(patrimonio_total),
            productos=productos,
        )

    def obtener_kardex_historico(
        self,
        session: Session,
        *,
        producto_id: UUID,
        fecha_inicio: date | None = None,
        fecha_fin: date | None = None,
        sucursal_id: UUID | None = None,
    ) -> ReporteInventarioKardexRead:
        empresa_scope = self._empresa_scope()
        hoy = date.today()
        inicio = fecha_inicio or (hoy - timedelta(days=365))
        fin = fecha_fin or hoy
        if inicio > fin:
            raise ValueError("fecha_inicio no puede ser mayor que fecha_fin.")

        stmt = (
            sa_select(
                col(MovimientoInventario.fecha),
                col(MovimientoInventario.tipo_movimiento),
                col(MovimientoInventario.referencia_documento),
                col(MovimientoInventarioDetalle.cantidad),
                col(MovimientoInventarioDetalle.costo_unitario),
            )
            .select_from(MovimientoInventarioDetalle)
            .join(
                MovimientoInventario,
                col(MovimientoInventario.id)
                == col(MovimientoInventarioDetalle.movimiento_inventario_id),
            )
            .where(
                col(MovimientoInventarioDetalle.activo).is_(True),
                col(MovimientoInventario.activo).is_(True),
                col(MovimientoInventario.estado)
                == EstadoMovimientoInventario.CONFIRMADO,
                col(MovimientoInventarioDetalle.producto_id) == producto_id,
                col(MovimientoInventario.fecha) >= inicio,
                col(MovimientoInventario.fecha) <= fin,
            )
            .order_by(
                col(MovimientoInventario.fecha).asc(),
                col(MovimientoInventario.creado_en).asc(),
                col(MovimientoInventarioDetalle.id).asc(),
            )
        )
        if sucursal_id is not None or empresa_scope is not None:
            stmt = stmt.join(
                Bodega, col(Bodega.id) == col(MovimientoInventario.bodega_id)
            ).where(col(Bodega.activo).is_(True))
            if empresa_scope is not None:
                stmt = stmt.where(col(Bodega.empresa_id) == empresa_scope)
            if sucursal_id is not None:
                stmt = stmt.where(col(Bodega.sucursal_id) == sucursal_id)

        rows = session.execute(stmt).all()
        saldo = Decimal("0.0000")
        movimientos: list[ReporteInventarioKardexMovimientoRead] = []
        for (
            mov_fecha,
            tipo_movimiento,
            referencia_documento,
            cantidad,
            costo_unitario,
        ) in rows:
            cantidad_d = q4(self._d(cantidad))
            costo_d = q4(self._d(costo_unitario))
            if tipo_movimiento in {
                TipoMovimientoInventario.EGRESO,
                TipoMovimientoInventario.TRANSFERENCIA,
            }:
                saldo = q4(saldo - cantidad_d)
                tipo_kardex = TipoMovimientoKardex.EGRESO
                if (referencia_documento or "").startswith("VENTA:"):
                    tipo_kardex = TipoMovimientoKardex.VENTA
            else:
                saldo = q4(saldo + cantidad_d)
                tipo_kardex = TipoMovimientoKardex.INGRESO

            movimientos.append(
                ReporteInventarioKardexMovimientoRead(
                    fecha=mov_fecha,
                    tipo_movimiento=tipo_kardex,
                    cantidad=cantidad_d,
                    costo_unitario=costo_d,
                    saldo_cantidad=saldo,
                )
            )

        return ReporteInventarioKardexRead(
            producto_id=producto_id,
            fecha_inicio=inicio,
            fecha_fin=fin,
            movimientos=movimientos,
        )
