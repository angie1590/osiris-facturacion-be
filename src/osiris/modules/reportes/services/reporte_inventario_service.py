from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import func
from sqlmodel import Session, select

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

    def obtener_valoracion_inventario(self, session: Session) -> ReporteInventarioValoracionRead:
        empresa_scope = self._empresa_scope()
        cantidad_expr = func.coalesce(func.sum(InventarioStock.cantidad_actual), 0)
        valor_expr = func.coalesce(
            func.sum(InventarioStock.cantidad_actual * InventarioStock.costo_promedio_vigente),
            0,
        )

        stmt = (
            select(
                Producto.id,
                Producto.nombre,
                cantidad_expr.label("cantidad_actual"),
                valor_expr.label("valor_total"),
            )
            .select_from(Producto)
            .join(
                InventarioStock,
                (InventarioStock.producto_id == Producto.id) & (InventarioStock.activo.is_(True)),
                isouter=True,
            )
            .where(Producto.activo.is_(True))
            .group_by(Producto.id, Producto.nombre)
            .order_by(Producto.nombre.asc())
        )
        if empresa_scope is not None:
            stmt = (
                stmt.join(Bodega, Bodega.id == InventarioStock.bodega_id)
                .where(
                    Bodega.activo.is_(True),
                    Bodega.empresa_id == empresa_scope,
                )
            )

        rows = session.exec(stmt).all()

        productos: list[ReporteInventarioValoracionItemRead] = []
        patrimonio_total = Decimal("0.00")
        for producto_id, nombre, cantidad_actual, valor_total in rows:
            cantidad_d = q4(self._d(cantidad_actual))
            valor_d = q2(self._d(valor_total))
            patrimonio_total = q2(patrimonio_total + valor_d)
            costo_promedio = q4(valor_d / cantidad_d) if cantidad_d > Decimal("0") else Decimal("0.0000")

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
        producto_id,
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
            select(
                MovimientoInventario.fecha,
                MovimientoInventario.tipo_movimiento,
                MovimientoInventario.referencia_documento,
                MovimientoInventarioDetalle.cantidad,
                MovimientoInventarioDetalle.costo_unitario,
            )
            .select_from(MovimientoInventarioDetalle)
            .join(MovimientoInventario, MovimientoInventario.id == MovimientoInventarioDetalle.movimiento_inventario_id)
            .where(
                MovimientoInventarioDetalle.activo.is_(True),
                MovimientoInventario.activo.is_(True),
                MovimientoInventario.estado == EstadoMovimientoInventario.CONFIRMADO,
                MovimientoInventarioDetalle.producto_id == producto_id,
                MovimientoInventario.fecha >= inicio,
                MovimientoInventario.fecha <= fin,
            )
            .order_by(
                MovimientoInventario.fecha.asc(),
                MovimientoInventario.creado_en.asc(),
                MovimientoInventarioDetalle.id.asc(),
            )
        )
        if sucursal_id is not None or empresa_scope is not None:
            stmt = stmt.join(Bodega, Bodega.id == MovimientoInventario.bodega_id).where(Bodega.activo.is_(True))
            if empresa_scope is not None:
                stmt = stmt.where(Bodega.empresa_id == empresa_scope)
            if sucursal_id is not None:
                stmt = stmt.where(Bodega.sucursal_id == sucursal_id)

        rows = session.exec(stmt).all()
        saldo = Decimal("0.0000")
        movimientos: list[ReporteInventarioKardexMovimientoRead] = []
        for mov_fecha, tipo_movimiento, referencia_documento, cantidad, costo_unitario in rows:
            cantidad_d = q4(self._d(cantidad))
            costo_d = q4(self._d(costo_unitario))
            if tipo_movimiento in {TipoMovimientoInventario.EGRESO, TipoMovimientoInventario.TRANSFERENCIA}:
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
