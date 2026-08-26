from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import String, cast, func
from sqlmodel import Session, select

from osiris.core.company_scope import resolve_company_scope
from osiris.modules.sri.core_sri.models import EstadoVenta, Venta, VentaDetalle
from osiris.modules.sri.core_sri.schemas import q2
from osiris.modules.inventario.movimientos.models import (
    EstadoMovimientoInventario,
    InventarioStock,
    MovimientoInventario,
    MovimientoInventarioDetalle,
    TipoMovimientoInventario,
)
from osiris.modules.reportes.schemas import (
    AgrupacionTendencia,
    ReporteRentabilidadClienteRead,
    ReporteRentabilidadTransaccionRead,
    ReporteTopProductoRead,
    ReporteVentasPorVendedorRead,
    ReporteVentasResumenRead,
    ReporteVentasTendenciaRead,
)
from osiris.modules.common.punto_emision.entity import PuntoEmision
from osiris.modules.common.usuario.entity import Usuario
from osiris.modules.inventario.producto.entity import Producto


class ReportesVentasService:
    @staticmethod
    def _empresa_scope() -> UUID | None:
        return resolve_company_scope()

    @staticmethod
    def _d(value: object, default: str = "0.00") -> Decimal:
        if value is None:
            return Decimal(default)
        return Decimal(str(value))

    @staticmethod
    def _to_period_date(value: object) -> date:
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            return date.fromisoformat(value[:10])
        raise ValueError("No se pudo convertir el periodo de tendencia a fecha")

    @staticmethod
    def _bucket_expr(session: Session, agrupacion: AgrupacionTendencia):
        bind = session.get_bind()
        dialect = bind.dialect.name if bind is not None else ""
        if dialect == "postgresql":
            if agrupacion == AgrupacionTendencia.ANUAL:
                return func.date_trunc("year", Venta.fecha_emision)
            if agrupacion == AgrupacionTendencia.MENSUAL:
                return func.date_trunc("month", Venta.fecha_emision)
            return func.date_trunc("day", Venta.fecha_emision)
        if agrupacion == AgrupacionTendencia.ANUAL:
            return func.strftime("%Y-01-01", Venta.fecha_emision)
        if agrupacion == AgrupacionTendencia.MENSUAL:
            return func.strftime("%Y-%m-01", Venta.fecha_emision)
        return func.date(Venta.fecha_emision)

    @staticmethod
    def _ref_venta(venta_id: UUID) -> str:
        return f"VENTA:{venta_id}"

    def _costos_historicos_por_venta(
        self,
        session: Session,
        *,
        venta_ids: list[UUID],
    ) -> dict[UUID, Decimal]:
        if not venta_ids:
            return {}

        refs = [self._ref_venta(venta_id) for venta_id in venta_ids]
        costo_expr = func.coalesce(
            func.sum(MovimientoInventarioDetalle.cantidad * MovimientoInventarioDetalle.costo_unitario),
            0,
        )
        stmt = (
            select(
                MovimientoInventario.referencia_documento,
                costo_expr.label("costo_total"),
            )
            .select_from(MovimientoInventario)
            .join(
                MovimientoInventarioDetalle,
                MovimientoInventarioDetalle.movimiento_inventario_id == MovimientoInventario.id,
            )
            .where(
                MovimientoInventario.activo.is_(True),
                MovimientoInventarioDetalle.activo.is_(True),
                MovimientoInventario.estado == EstadoMovimientoInventario.CONFIRMADO,
                MovimientoInventario.tipo_movimiento == TipoMovimientoInventario.EGRESO,
                MovimientoInventario.referencia_documento.in_(refs),
            )
            .group_by(MovimientoInventario.referencia_documento)
        )

        by_ref: dict[str, Decimal] = {
            str(referencia_documento): self._d(costo_total)
            for referencia_documento, costo_total in session.exec(stmt).all()
        }
        return {
            venta_id: by_ref.get(self._ref_venta(venta_id), Decimal("0.00"))
            for venta_id in venta_ids
        }

    def obtener_resumen_ventas(
        self,
        session: Session,
        *,
        fecha_inicio: date,
        fecha_fin: date,
        punto_emision_id: UUID | None = None,
        sucursal_id: UUID | None = None,
    ) -> ReporteVentasResumenRead:
        empresa_scope = self._empresa_scope()
        filtros = [
            Venta.activo.is_(True),
            Venta.estado != EstadoVenta.ANULADA,
            Venta.fecha_emision >= fecha_inicio,
            Venta.fecha_emision <= fecha_fin,
        ]
        if empresa_scope is not None:
            filtros.append(Venta.empresa_id == empresa_scope)
        if punto_emision_id is not None:
            filtros.append(Venta.punto_emision_id == punto_emision_id)
        if sucursal_id is not None:
            filtros.append(PuntoEmision.sucursal_id == sucursal_id)

        stmt = select(
            func.coalesce(func.sum(Venta.subtotal_0), 0),
            func.coalesce(func.sum(Venta.subtotal_12), 0),
            func.coalesce(func.sum(Venta.monto_iva), 0),
            func.coalesce(func.sum(Venta.valor_total), 0),
            func.count(Venta.id),
        ).select_from(Venta)
        if sucursal_id is not None:
            stmt = stmt.join(PuntoEmision, PuntoEmision.id == Venta.punto_emision_id)
        stmt = stmt.where(*filtros)
        subtotal_0, subtotal_12, monto_iva, total, total_ventas = session.exec(stmt).one()

        return ReporteVentasResumenRead(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            punto_emision_id=punto_emision_id,
            sucursal_id=sucursal_id,
            subtotal_0=q2(self._d(subtotal_0)),
            subtotal_12=q2(self._d(subtotal_12)),
            monto_iva=q2(self._d(monto_iva)),
            total=q2(self._d(total)),
            total_ventas=int(total_ventas or 0),
        )

    def obtener_top_productos(
        self,
        session: Session,
        *,
        fecha_inicio: date | None = None,
        fecha_fin: date | None = None,
        punto_emision_id: UUID | None = None,
        limite: int = 10,
    ) -> list[ReporteTopProductoRead]:
        empresa_scope = self._empresa_scope()
        limite_efectivo = max(1, min(limite, 100))
        filtros = [
            Venta.activo.is_(True),
            VentaDetalle.activo.is_(True),
            Producto.activo.is_(True),
            Venta.estado != EstadoVenta.ANULADA,
        ]
        if empresa_scope is not None:
            filtros.append(Venta.empresa_id == empresa_scope)
        if fecha_inicio is not None:
            filtros.append(Venta.fecha_emision >= fecha_inicio)
        if fecha_fin is not None:
            filtros.append(Venta.fecha_emision <= fecha_fin)
        if punto_emision_id is not None:
            filtros.append(Venta.punto_emision_id == punto_emision_id)

        costo_promedio_subq = (
            select(
                InventarioStock.producto_id.label("producto_id"),
                func.coalesce(func.avg(InventarioStock.costo_promedio_vigente), 0).label("costo_promedio"),
            )
            .where(InventarioStock.activo.is_(True))
            .group_by(InventarioStock.producto_id)
            .subquery()
        )

        ingreso_bruto_expr = func.coalesce(func.sum(VentaDetalle.precio_unitario * VentaDetalle.cantidad), 0)
        cantidad_expr = func.coalesce(func.sum(VentaDetalle.cantidad), 0)

        stmt = (
            select(
                Producto.id,
                Producto.nombre,
                cantidad_expr.label("cantidad_vendida"),
                ingreso_bruto_expr.label("total_dolares_vendido"),
                func.coalesce(costo_promedio_subq.c.costo_promedio, 0).label("costo_promedio"),
            )
            .select_from(VentaDetalle)
            .join(Venta, Venta.id == VentaDetalle.venta_id)
            .join(Producto, Producto.id == VentaDetalle.producto_id)
            .outerjoin(
                costo_promedio_subq,
                costo_promedio_subq.c.producto_id == Producto.id,
            )
            .where(*filtros)
            .group_by(
                Producto.id,
                Producto.nombre,
                costo_promedio_subq.c.costo_promedio,
            )
            .order_by(cantidad_expr.desc())
            .limit(limite_efectivo)
        )

        rows = session.exec(stmt).all()
        items: list[ReporteTopProductoRead] = []
        for producto_id, nombre, cantidad, total_vendido, costo_promedio in rows:
            cantidad_d = self._d(cantidad, default="0.0000")
            total_vendido_d = self._d(total_vendido)
            costo_promedio_d = self._d(costo_promedio, default="0.0000")
            ganancia = q2(total_vendido_d - (costo_promedio_d * cantidad_d))
            items.append(
                ReporteTopProductoRead(
                    producto_id=producto_id,
                    nombre_producto=nombre,
                    cantidad_vendida=Decimal(str(cantidad_d)),
                    total_dolares_vendido=q2(total_vendido_d),
                    ganancia_bruta_estimada=ganancia,
                )
            )
        return items

    def obtener_tendencias_ventas(
        self,
        session: Session,
        *,
        fecha_inicio: date,
        fecha_fin: date,
        agrupacion: AgrupacionTendencia,
    ) -> list[ReporteVentasTendenciaRead]:
        empresa_scope = self._empresa_scope()
        bucket = self._bucket_expr(session, agrupacion)
        stmt = (
            select(
                bucket.label("periodo"),
                func.coalesce(func.sum(Venta.valor_total), 0).label("total"),
                func.count(Venta.id).label("total_ventas"),
            )
            .where(
                Venta.activo.is_(True),
                Venta.estado != EstadoVenta.ANULADA,
                Venta.fecha_emision >= fecha_inicio,
                Venta.fecha_emision <= fecha_fin,
            )
            .group_by(bucket)
            .order_by(bucket.asc())
        )
        if empresa_scope is not None:
            stmt = stmt.where(Venta.empresa_id == empresa_scope)
        rows = session.exec(stmt).all()
        return [
            ReporteVentasTendenciaRead(
                periodo=self._to_period_date(periodo),
                total=q2(self._d(total)),
                total_ventas=int(total_ventas or 0),
            )
            for periodo, total, total_ventas in rows
        ]

    def obtener_ventas_por_vendedor(
        self,
        session: Session,
        *,
        fecha_inicio: date | None = None,
        fecha_fin: date | None = None,
    ) -> list[ReporteVentasPorVendedorRead]:
        empresa_scope = self._empresa_scope()
        filtros = [
            Venta.activo.is_(True),
            Venta.estado != EstadoVenta.ANULADA,
        ]
        if empresa_scope is not None:
            filtros.append(Venta.empresa_id == empresa_scope)
        if fecha_inicio is not None:
            filtros.append(Venta.fecha_emision >= fecha_inicio)
        if fecha_fin is not None:
            filtros.append(Venta.fecha_emision <= fecha_fin)

        join_cond = cast(Usuario.id, String) == Venta.created_by
        vendedor_expr = func.coalesce(Usuario.username, Venta.created_by, "SIN_USUARIO")

        stmt = (
            select(
                Usuario.id.label("usuario_id"),
                vendedor_expr.label("vendedor"),
                func.coalesce(func.sum(Venta.valor_total), 0).label("total_vendido"),
                func.count(Venta.id).label("facturas_emitidas"),
            )
            .select_from(Venta)
            .outerjoin(Usuario, join_cond)
            .where(*filtros)
            .group_by(Usuario.id, vendedor_expr)
            .order_by(func.sum(Venta.valor_total).desc(), vendedor_expr.asc())
        )
        rows = session.exec(stmt).all()
        return [
            ReporteVentasPorVendedorRead(
                usuario_id=usuario_id,
                vendedor=str(vendedor),
                total_vendido=q2(self._d(total_vendido)),
                facturas_emitidas=int(facturas_emitidas or 0),
            )
            for usuario_id, vendedor, total_vendido, facturas_emitidas in rows
        ]

    def obtener_rentabilidad_por_cliente(
        self,
        session: Session,
        *,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> list[ReporteRentabilidadClienteRead]:
        empresa_scope = self._empresa_scope()
        ventas = list(
            session.exec(
                select(Venta.id, Venta.cliente_id, Venta.subtotal_sin_impuestos)
                .where(
                    Venta.activo.is_(True),
                    Venta.estado != EstadoVenta.ANULADA,
                    Venta.fecha_emision >= fecha_inicio,
                    Venta.fecha_emision <= fecha_fin,
                    *( [Venta.empresa_id == empresa_scope] if empresa_scope is not None else [] ),
                )
            ).all()
        )
        venta_ids = [venta_id for venta_id, _, _ in ventas]
        costos_por_venta = self._costos_historicos_por_venta(session, venta_ids=venta_ids)

        acumulado: dict[UUID | None, dict[str, Decimal | int]] = {}
        for venta_id, cliente_id, subtotal in ventas:
            if cliente_id not in acumulado:
                acumulado[cliente_id] = {
                    "total_vendido": Decimal("0.00"),
                    "costo_total": Decimal("0.00"),
                    "total_facturas": 0,
                }
            bucket = acumulado[cliente_id]
            bucket["total_vendido"] = self._d(bucket["total_vendido"]) + self._d(subtotal)
            bucket["costo_total"] = self._d(bucket["costo_total"]) + costos_por_venta.get(venta_id, Decimal("0.00"))
            bucket["total_facturas"] = int(bucket["total_facturas"]) + 1

        items: list[ReporteRentabilidadClienteRead] = []
        for cliente_id, data in acumulado.items():
            total_vendido = q2(self._d(data["total_vendido"]))
            costo_total = q2(self._d(data["costo_total"]))
            utilidad = q2(total_vendido - costo_total)
            margen = Decimal("0.00")
            if total_vendido != Decimal("0.00"):
                margen = q2((utilidad / total_vendido) * Decimal("100"))

            items.append(
                ReporteRentabilidadClienteRead(
                    cliente_id=cliente_id,
                    total_vendido=total_vendido,
                    costo_historico_total=costo_total,
                    utilidad_bruta_dolares=utilidad,
                    margen_porcentual=margen,
                    total_facturas=int(data["total_facturas"]),
                )
            )

        return sorted(items, key=lambda item: item.total_vendido, reverse=True)

    def obtener_rentabilidad_transaccional(
        self,
        session: Session,
        *,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> list[ReporteRentabilidadTransaccionRead]:
        empresa_scope = self._empresa_scope()
        ventas = list(
            session.exec(
                select(Venta.id, Venta.cliente_id, Venta.fecha_emision, Venta.subtotal_sin_impuestos)
                .where(
                    Venta.activo.is_(True),
                    Venta.estado != EstadoVenta.ANULADA,
                    Venta.fecha_emision >= fecha_inicio,
                    Venta.fecha_emision <= fecha_fin,
                    *( [Venta.empresa_id == empresa_scope] if empresa_scope is not None else [] ),
                )
                .order_by(Venta.fecha_emision.asc(), Venta.creado_en.asc())
            ).all()
        )
        venta_ids = [venta_id for venta_id, _, _, _ in ventas]
        costos_por_venta = self._costos_historicos_por_venta(session, venta_ids=venta_ids)

        items: list[ReporteRentabilidadTransaccionRead] = []
        for venta_id, cliente_id, fecha_emision, subtotal in ventas:
            subtotal_d = q2(self._d(subtotal))
            costo_total = q2(costos_por_venta.get(venta_id, Decimal("0.00")))
            utilidad = q2(subtotal_d - costo_total)
            margen = Decimal("0.00")
            if subtotal_d != Decimal("0.00"):
                margen = q2((utilidad / subtotal_d) * Decimal("100"))

            items.append(
                ReporteRentabilidadTransaccionRead(
                    venta_id=venta_id,
                    cliente_id=cliente_id,
                    fecha_emision=fecha_emision,
                    subtotal_venta=subtotal_d,
                    costo_historico_total=costo_total,
                    utilidad_bruta_dolares=utilidad,
                    margen_porcentual=margen,
                )
            )
        return items
