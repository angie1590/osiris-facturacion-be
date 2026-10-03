from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import BackgroundTasks
from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlmodel import Session, col, select

from osiris.core.company_scope import ensure_entity_belongs_to_selected_company, resolve_company_scope
from osiris.modules.sri.core_sri.services.template_method import TemplateMethodService
from osiris.modules.common.empresa.entity import RegimenTributario
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.punto_emision.entity import (
    ModalidadPuntoEmision,
    PuntoEmision,
    TipoDocumentoSRI,
)
from osiris.modules.common.punto_emision.service import PuntoEmisionService
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.ventas.strategies.emision_rimpe_strategy import EmisionRimpeStrategy
from osiris.modules.sri.core_sri.models import (
    CuentaPorCobrar,
    EstadoSriDocumento,
    EstadoCuentaPorCobrar,
    EstadoVenta,
    TipoDocumentoElectronico,
    TipoEmisionVenta,
    Venta,
    VentaDetalle,
    VentaDetalleImpuesto,
    VentaEstadoHistorial,
)
from osiris.modules.sri.core_sri.types import TipoImpuestoMVP
from osiris.modules.sri.core_sri.all_schemas import (
    ImpuestoAplicadoInput,
    VentaCompraDetalleCreate,
    VentaCreate,
    VentaDetalleImpuestoRead,
    VentaDetalleRead,
    VentaRead,
    VentaRegistroCreate,
    VentaUpdate,
    q2,
)
from osiris.modules.sri.facturacion_electronica.services.orquestador_fe_service import OrquestadorFEService
from osiris.modules.sri.facturacion_electronica.services.venta_sri_async_service import VentaSriAsyncService
from osiris.modules.sri.medidas_temporales.service import MedidaTributariaService
from osiris.modules.common.audit_log.entity import AuditAction, AuditLog
from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.modules.inventario.movimientos.models import (
    EstadoMovimientoInventario,
    InventarioStock,
    MovimientoInventario,
    MovimientoInventarioDetalle,
    TipoMovimientoInventario,
)
from osiris.modules.inventario.movimientos.schemas import (
    MovimientoInventarioCreate,
    MovimientoInventarioDetalleCreate,
)
from osiris.modules.inventario.movimientos.services.movimiento_inventario_service import MovimientoInventarioService, q4
from osiris.modules.inventario.bodega.entity import Bodega
from osiris.modules.inventario.producto.entity import Producto, ProductoImpuesto
from osiris.modules.inventario.producto_impuesto.scope import resolve_product_tax_company
from osiris.utils.pagination import PaginationMeta, build_pagination_meta


class VentaService(TemplateMethodService[VentaCreate, Venta]):
    def __init__(self, emision_rimpe_strategy: EmisionRimpeStrategy | None = None) -> None:
        self.movimiento_service = MovimientoInventarioService()
        self.punto_emision_service = PuntoEmisionService()
        self.venta_sri_async_service = VentaSriAsyncService()
        self.orquestador_fe_service = OrquestadorFEService(venta_sri_service=self.venta_sri_async_service)
        self.emision_rimpe_strategy = emision_rimpe_strategy or EmisionRimpeStrategy()
        self.medida_tributaria_service = MedidaTributariaService()

    @staticmethod
    def _es_session_real(session: Session) -> bool:
        return isinstance(session, Session)

    @staticmethod
    def _empresa_scope(empresa_id: UUID | None = None) -> UUID | None:
        return resolve_company_scope(requested_company_id=empresa_id)

    @staticmethod
    def _snapshot_impuestos_producto(
        session: Session,
        producto_id: UUID,
        empresa_id: UUID,
    ) -> list[ImpuestoAplicadoInput]:
        stmt = select(ProductoImpuesto).where(
            col(ProductoImpuesto.producto_id) == producto_id,
            col(ProductoImpuesto.empresa_id) == empresa_id,
            col(ProductoImpuesto.activo).is_(True),
        )
        impuestos = list(session.exec(stmt).all())
        if not impuestos:
            raise HTTPException(
                status_code=400,
                detail=f"El producto {producto_id} no tiene impuestos configurados.",
            )

        snapshots: list[ImpuestoAplicadoInput] = []
        for impuesto in impuestos:
            if impuesto.codigo_impuesto_sri == "2":
                tipo = TipoImpuestoMVP.IVA
            elif impuesto.codigo_impuesto_sri == "3":
                tipo = TipoImpuestoMVP.ICE
            else:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Impuesto {impuesto.id} del producto {producto_id} no es compatible "
                        "con catalogo MVP (solo IVA/ICE)."
                    ),
                )

            snapshots.append(
                ImpuestoAplicadoInput(
                    tipo_impuesto=tipo,
                    codigo_impuesto_sri=impuesto.codigo_impuesto_sri,
                    codigo_porcentaje_sri=impuesto.codigo_porcentaje_sri,
                    tarifa=impuesto.tarifa,
                )
            )
        return snapshots

    def _resolver_empresa_para_snapshot(self, session: Session, payload: VentaRegistroCreate) -> UUID:
        empresa_id = resolve_company_scope()
        if empresa_id is not None:
            resolve_company_scope(requested_company_id=payload.empresa_id)
            if payload.bodega_id is not None:
                bodega = session.get(Bodega, payload.bodega_id)
                if not bodega or not bodega.activo:
                    raise HTTPException(status_code=404, detail="Bodega no encontrada o inactiva.")
                if bodega.empresa_id != empresa_id:
                    raise HTTPException(status_code=403, detail="La bodega no pertenece a la empresa autenticada.")
            if payload.punto_emision_id is not None:
                punto = session.get(PuntoEmision, payload.punto_emision_id)
                if not punto or not punto.activo:
                    raise HTTPException(status_code=404, detail="Punto de emisión no encontrado o inactivo.")
                sucursal = session.get(Sucursal, punto.sucursal_id)
                if not sucursal or not sucursal.activo or sucursal.empresa_id != empresa_id:
                    raise HTTPException(status_code=403, detail="El punto de emisión no pertenece a la empresa autenticada.")
        else:
            if payload.bodega_id is not None:
                bodega = session.get(Bodega, payload.bodega_id)
                if not bodega or not bodega.activo:
                    raise HTTPException(status_code=404, detail="Bodega no encontrada o inactiva.")
                empresa_id = bodega.empresa_id
            if payload.punto_emision_id is not None:
                punto = session.get(PuntoEmision, payload.punto_emision_id)
                if not punto or not punto.activo:
                    raise HTTPException(status_code=404, detail="Punto de emisión no encontrado o inactivo.")
                sucursal = session.get(Sucursal, punto.sucursal_id)
                if not sucursal or not sucursal.activo:
                    raise HTTPException(status_code=404, detail="Sucursal del punto de emisión no encontrada o inactiva.")
                if empresa_id is not None and empresa_id != sucursal.empresa_id:
                    raise HTTPException(status_code=403, detail="Bodega y punto de emisión pertenecen a empresas distintas.")
                empresa_id = sucursal.empresa_id
            if empresa_id is None:
                inferred_companies = {
                    resolve_product_tax_company(session, detalle.producto_id).id
                    for detalle in payload.detalles
                }
                if len(inferred_companies) == 1:
                    empresa_id = next(iter(inferred_companies))
                else:
                    raise HTTPException(
                        status_code=409,
                        detail="No se puede resolver una empresa única para los impuestos de la venta.",
                    )
            if payload.empresa_id is not None and payload.empresa_id != empresa_id:
                raise HTTPException(status_code=403, detail="La empresa del request no coincide con el contexto resuelto.")

        empresa = session.get(Empresa, empresa_id)
        if not empresa or not empresa.activo:
            raise HTTPException(status_code=403, detail="La empresa seleccionada no existe o está inactiva.")
        return empresa_id

    def hidratar_venta_desde_productos(self, session: Session, payload: VentaRegistroCreate) -> VentaCreate:
        empresa_id = self._resolver_empresa_para_snapshot(session, payload)
        detalles: list[VentaCompraDetalleCreate] = []
        for detalle in payload.detalles:
            producto = session.get(Producto, detalle.producto_id)
            if not producto or not producto.activo:
                raise HTTPException(
                    status_code=404,
                    detail=f"Producto {detalle.producto_id} no encontrado o inactivo.",
                )

            impuestos = self._snapshot_impuestos_producto(session, detalle.producto_id, empresa_id)
            detalles.append(
                VentaCompraDetalleCreate(
                    producto_id=detalle.producto_id,
                    descripcion=detalle.descripcion,
                    cantidad=detalle.cantidad,
                    precio_unitario=detalle.precio_unitario,
                    descuento=detalle.descuento,
                    es_actividad_excluida=detalle.es_actividad_excluida,
                    impuestos=impuestos,
                )
            )

        return VentaCreate(
            cliente_id=payload.cliente_id,
            empresa_id=empresa_id,
            punto_emision_id=payload.punto_emision_id,
            fecha_emision=payload.fecha_emision,
            bodega_id=payload.bodega_id,
            tipo_identificacion_comprador=payload.tipo_identificacion_comprador,
            identificacion_comprador=payload.identificacion_comprador,
            forma_pago=payload.forma_pago,
            tipo_emision=payload.tipo_emision,
            regimen_emisor=payload.regimen_emisor,
            usuario_auditoria=payload.usuario_auditoria,
            detalles=detalles,
        )

    @staticmethod
    def _validar_iva_rimpe_negocio_popular(
        payload: VentaCreate,
        *,
        tipo_emision: TipoEmisionVenta,
    ) -> None:
        EmisionRimpeStrategy.validar_iva_rimpe_negocio_popular(payload, tipo_emision=tipo_emision)

    def _resolver_contexto_tributario(self, session: Session, payload: VentaCreate) -> tuple[UUID | None, RegimenTributario, TipoEmisionVenta]:
        empresa_id = resolve_company_scope()
        if empresa_id is not None:
            resolve_company_scope(requested_company_id=payload.empresa_id)
            if payload.bodega_id is not None:
                bodega = session.get(Bodega, payload.bodega_id)
                if not bodega or not bodega.activo:
                    raise HTTPException(status_code=404, detail="Bodega no encontrada o inactiva.")
                if bodega.empresa_id != empresa_id:
                    raise HTTPException(status_code=403, detail="La bodega no pertenece a la empresa autenticada.")
            if payload.punto_emision_id is not None:
                punto = session.get(PuntoEmision, payload.punto_emision_id)
                if not punto or not punto.activo:
                    raise HTTPException(status_code=404, detail="Punto de emisión no encontrado o inactivo.")
                sucursal = session.get(Sucursal, punto.sucursal_id)
                if not sucursal or not sucursal.activo or sucursal.empresa_id != empresa_id:
                    raise HTTPException(status_code=403, detail="El punto de emisión no pertenece a la empresa autenticada.")
        else:
            if payload.bodega_id is not None:
                bodega = session.get(Bodega, payload.bodega_id)
                if not bodega or not bodega.activo:
                    raise HTTPException(status_code=404, detail="Bodega no encontrada o inactiva.")
                empresa_id = bodega.empresa_id
            if payload.punto_emision_id is not None:
                punto = session.get(PuntoEmision, payload.punto_emision_id)
                if not punto or not punto.activo:
                    raise HTTPException(status_code=404, detail="Punto de emisión no encontrado o inactivo.")
                sucursal = session.get(Sucursal, punto.sucursal_id)
                if not sucursal or not sucursal.activo:
                    raise HTTPException(status_code=404, detail="Sucursal del punto de emisión no encontrada o inactiva.")
                if empresa_id is not None and empresa_id != sucursal.empresa_id:
                    raise HTTPException(status_code=403, detail="Bodega y punto de emisión pertenecen a empresas distintas.")
                empresa_id = sucursal.empresa_id
            if empresa_id is None:
                inferred_companies = {
                    resolve_product_tax_company(session, detalle.producto_id).id
                    for detalle in payload.detalles
                }
                if len(inferred_companies) == 1:
                    empresa_id = next(iter(inferred_companies))
                else:
                    raise HTTPException(
                        status_code=409,
                        detail="No se puede resolver una empresa única para la venta.",
                    )
            if payload.empresa_id is not None and payload.empresa_id != empresa_id:
                raise HTTPException(status_code=403, detail="La empresa del request no coincide con el contexto resuelto.")

        empresa = session.get(Empresa, empresa_id)
        if not empresa or not empresa.activo:
            raise HTTPException(status_code=403, detail="La empresa seleccionada no existe o está inactiva.")
        trusted_payload = payload.model_copy(update={"empresa_id": empresa_id})
        return self.emision_rimpe_strategy.resolver_contexto_tributario(session, trusted_payload)

    def _resolver_secuencial_formateado(
        self,
        session: Session,
        payload: VentaCreate,
        empresa_id_actual: UUID | None,
    ) -> tuple[UUID | None, str | None]:
        if payload.secuencial_formateado is not None:
            raise HTTPException(status_code=400, detail="El secuencial se asigna únicamente al emitir la venta.")
        if payload.punto_emision_id is None:
            return empresa_id_actual, None

        punto = session.get(PuntoEmision, payload.punto_emision_id)
        if not punto or not punto.activo:
            raise HTTPException(status_code=404, detail="Punto de emisión no encontrado o inactivo.")

        sucursal = session.get(Sucursal, punto.sucursal_id)
        if not sucursal or not sucursal.activo:
            raise HTTPException(status_code=404, detail="Sucursal del punto de emisión no encontrada o inactiva.")

        if empresa_id_actual is not None and sucursal.empresa_id != empresa_id_actual:
            raise HTTPException(
                status_code=400,
                detail="El punto de emisión no pertenece a la empresa indicada en la venta.",
            )
        empresa_id = empresa_id_actual or sucursal.empresa_id
        expected_mode = (
            ModalidadPuntoEmision.ELECTRONICA
            if payload.tipo_emision == TipoEmisionVenta.ELECTRONICA
            else ModalidadPuntoEmision.FISICA
        )
        if punto.modalidad_emision != expected_mode:
            raise HTTPException(
                status_code=409,
                detail=f"El punto de emisión es {punto.modalidad_emision.value}; la venta requiere {expected_mode.value}.",
            )
        if not sucursal.codigo.isdigit() or len(sucursal.codigo) != 3 or not punto.codigo.isdigit() or len(punto.codigo) != 3:
            raise HTTPException(status_code=400, detail="Sucursal y punto de emisión deben usar códigos SRI de tres dígitos.")
        return empresa_id, None

    def _asignar_secuencial_venta(self, session: Session, venta: Venta, usuario_auditoria: str) -> None:
        point_branch = self._validar_punto_venta(session, venta)
        if point_branch is None:
            return
        punto, sucursal = point_branch
        counter = self.punto_emision_service._get_or_create_locked_secuencial(
            session,
            punto_emision_id=punto.id,
            tipo_documento=TipoDocumentoSRI.FACTURA,
            usuario_auditoria=usuario_auditoria,
        )
        next_number = counter.secuencial_actual + 1
        if next_number > 999999999:
            raise HTTPException(status_code=409, detail="La serie alcanzó el máximo secuencial SRI (999999999).")
        counter.secuencial_actual = next_number
        counter.usuario_auditoria = usuario_auditoria
        venta.secuencial_formateado = f"{sucursal.codigo}-{punto.codigo}-{next_number:09d}"
        session.add(counter)
        session.add(venta)

    @staticmethod
    def _validar_punto_venta(session: Session, venta: Venta) -> tuple[PuntoEmision, Sucursal] | None:
        if venta.punto_emision_id is None:
            if venta.tipo_emision == TipoEmisionVenta.ELECTRONICA:
                raise HTTPException(status_code=409, detail="Seleccione un punto de emisión electrónico para emitir la factura.")
            return None

        punto = session.get(PuntoEmision, venta.punto_emision_id)
        if not punto or not punto.activo:
            raise HTTPException(status_code=404, detail="Punto de emisión no encontrado o inactivo.")
        sucursal = session.get(Sucursal, punto.sucursal_id)
        if not sucursal or not sucursal.activo or sucursal.empresa_id != venta.empresa_id:
            raise HTTPException(status_code=409, detail="El punto de emisión no pertenece a la empresa de la venta.")
        expected_mode = (
            ModalidadPuntoEmision.ELECTRONICA
            if venta.tipo_emision == TipoEmisionVenta.ELECTRONICA
            else ModalidadPuntoEmision.FISICA
        )
        if punto.modalidad_emision != expected_mode:
            raise HTTPException(status_code=409, detail="La modalidad del punto no corresponde al tipo de emisión.")
        if not sucursal.codigo.isdigit() or len(sucursal.codigo) != 3 or not punto.codigo.isdigit() or len(punto.codigo) != 3:
            raise HTTPException(status_code=400, detail="Sucursal y punto de emisión deben usar códigos SRI de tres dígitos.")
        return punto, sucursal

    def _resolver_bodega_para_venta(self, session: Session, payload: VentaCreate) -> UUID:
        if payload.bodega_id is not None:
            bodega = session.get(Bodega, payload.bodega_id)
            if not bodega or not bodega.activo:
                raise HTTPException(status_code=404, detail="Bodega no encontrada o inactiva.")
            empresa_scope = self._empresa_scope(empresa_id=payload.empresa_id)
            if empresa_scope is not None and bodega.empresa_id != empresa_scope:
                raise HTTPException(status_code=403, detail="La bodega no pertenece a la empresa seleccionada.")
            return payload.bodega_id
        if not payload.detalles:
            raise HTTPException(status_code=400, detail="La venta no tiene detalles para orquestar inventario.")

        empresa_scope = self._empresa_scope(empresa_id=payload.empresa_id)
        producto_referencia = payload.detalles[0].producto_id
        stmt_stocks = (
            select(InventarioStock)
            .join(Bodega, col(Bodega.id) == col(InventarioStock.bodega_id))
            .where(
                col(InventarioStock.producto_id) == producto_referencia,
                col(InventarioStock.activo).is_(True),
                col(Bodega.activo).is_(True),
            )
        )
        if empresa_scope is not None:
            stmt_stocks = stmt_stocks.where(col(Bodega.empresa_id) == empresa_scope)
        stocks_referencia = list(session.exec(stmt_stocks).all())
        if not stocks_referencia:
            raise HTTPException(
                status_code=400,
                detail=f"No existe stock materializado para el producto {producto_referencia}.",
            )
        bodega_id = stocks_referencia[0].bodega_id

        for detalle in payload.detalles:
            stock_detalle = session.exec(
                select(InventarioStock).where(
                    col(InventarioStock.bodega_id) == bodega_id,
                    col(InventarioStock.producto_id) == detalle.producto_id,
                    col(InventarioStock.activo).is_(True),
                )
            ).first()
            if stock_detalle is None:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"El producto {detalle.producto_id} no tiene stock materializado "
                        f"en la bodega {bodega_id}."
                    ),
                )
        return bodega_id

    def _orquestar_egreso_inventario(self, session: Session, venta: Venta, payload: VentaCreate) -> None:
        if not self._es_session_real(session):
            return

        bodega_id = self._resolver_bodega_para_venta(session, payload)
        movimiento_payload = MovimientoInventarioCreate(
            bodega_id=bodega_id,
            tipo_movimiento=TipoMovimientoInventario.EGRESO,
            referencia_documento=f"VENTA:{venta.id}",
            usuario_auditoria=payload.usuario_auditoria,
            detalles=[
                MovimientoInventarioDetalleCreate(
                    producto_id=detalle.producto_id,
                    cantidad=detalle.cantidad,
                    costo_unitario=detalle.precio_unitario,
                )
                for detalle in payload.detalles
            ],
        )
        movimiento = self.movimiento_service.crear_movimiento_borrador(
            session,
            movimiento_payload,
            commit=False,
        )
        try:
            self.movimiento_service.confirmar_movimiento(
                session,
                movimiento.id,
                commit=False,
                rollback_on_error=False,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def _resolver_bodega_para_emitir_venta(
        self,
        session: Session,
        detalles: list[VentaDetalle],
    ) -> UUID:
        if not detalles:
            raise ValueError("No se puede emitir una venta sin detalles.")

        requerido_por_producto = self._agrupar_cantidad_por_producto(detalles)
        producto_referencia = detalles[0].producto_id

        empresa_scope = self._empresa_scope()
        stmt_stocks = (
            select(InventarioStock)
            .join(Bodega, col(Bodega.id) == col(InventarioStock.bodega_id))
            .where(
                col(InventarioStock.producto_id) == producto_referencia,
                col(InventarioStock.activo).is_(True),
                col(Bodega.activo).is_(True),
            )
        )
        if empresa_scope is not None:
            stmt_stocks = stmt_stocks.where(col(Bodega.empresa_id) == empresa_scope)
        stocks_referencia = list(session.exec(stmt_stocks).all())
        if not stocks_referencia:
            raise ValueError(f"Stock insuficiente para el producto {producto_referencia}")

        for stock_referencia in stocks_referencia:
            bodega_id = stock_referencia.bodega_id
            cumple_bodega = True
            for producto_id, cantidad_requerida in requerido_por_producto.items():
                stock_detalle = session.exec(
                    select(InventarioStock).where(
                        col(InventarioStock.bodega_id) == bodega_id,
                        col(InventarioStock.producto_id) == producto_id,
                        col(InventarioStock.activo).is_(True),
                    )
                ).one_or_none()
                if stock_detalle is None or q4(stock_detalle.cantidad_actual) - cantidad_requerida < Decimal("0.0000"):
                    cumple_bodega = False
                    break

            if cumple_bodega:
                return bodega_id

        raise ValueError(f"Stock insuficiente para el producto {producto_referencia}")

    @staticmethod
    def _agrupar_cantidad_por_producto(detalles: list[VentaDetalle]) -> dict[UUID, Decimal]:
        requerido_por_producto: dict[UUID, Decimal] = {}
        for detalle in detalles:
            requerido_por_producto.setdefault(detalle.producto_id, Decimal("0.0000"))
            requerido_por_producto[detalle.producto_id] = q4(
                requerido_por_producto[detalle.producto_id] + q4(detalle.cantidad)
            )
        return requerido_por_producto

    @staticmethod
    def _sincronizar_productos_desde_stock(session: Session, *, producto_ids: set[UUID]) -> None:
        if not producto_ids:
            return

        for producto_id in producto_ids:
            total_stock = session.exec(
                select(func.coalesce(func.sum(InventarioStock.cantidad_actual), Decimal("0.0000"))).where(
                    col(InventarioStock.producto_id) == producto_id,
                    col(InventarioStock.activo).is_(True),
                )
            ).one()
            producto = session.get(Producto, producto_id)
            if not producto:
                continue
            cantidad_decimal = q4(total_stock)
            if not producto.permite_fracciones and cantidad_decimal != cantidad_decimal.to_integral_value():
                raise ValueError(
                    f"Inconsistencia de fracciones para el producto {producto_id}: no permite fracciones y tiene stock {cantidad_decimal}."
                )
            producto.cantidad = cantidad_decimal
            session.add(producto)

        session.flush()

    def _validar_stock_para_emision(
        self,
        session: Session,
        *,
        bodega_id: UUID,
        detalles: list[VentaDetalle],
    ) -> None:
        requerido_por_producto = self._agrupar_cantidad_por_producto(detalles)
        self._sincronizar_productos_desde_stock(session, producto_ids=set(requerido_por_producto.keys()))

        for producto_id, cantidad_requerida in requerido_por_producto.items():
            producto = session.get(Producto, producto_id)
            if not producto or not producto.activo:
                raise ValueError(f"Stock insuficiente para el producto {producto_id}")

            if q4(producto.cantidad) - cantidad_requerida < Decimal("0.0000"):
                raise ValueError(f"Stock insuficiente para el producto {producto_id}")

            stock = session.exec(
                select(InventarioStock)
                .where(
                    col(InventarioStock.bodega_id) == bodega_id,
                    col(InventarioStock.producto_id) == producto_id,
                    col(InventarioStock.activo).is_(True),
                )
                .with_for_update()
            ).one_or_none()
            if stock is None:
                raise ValueError(f"Stock insuficiente para el producto {producto_id}")

            if q4(stock.cantidad_actual) - cantidad_requerida < Decimal("0.0000"):
                raise ValueError(f"Stock insuficiente para el producto {producto_id}")

    @staticmethod
    def _obtener_egreso_inventario_venta(session: Session, venta_id: UUID) -> tuple[MovimientoInventario | None, dict[UUID, Decimal]]:
        movimiento = session.exec(
            select(MovimientoInventario)
            .where(
                MovimientoInventario.referencia_documento == f"VENTA:{venta_id}",
                MovimientoInventario.tipo_movimiento == TipoMovimientoInventario.EGRESO,
                MovimientoInventario.estado == EstadoMovimientoInventario.CONFIRMADO,
                col(MovimientoInventario.activo).is_(True),
            )
            .order_by(col(MovimientoInventario.fecha).desc(), col(MovimientoInventario.creado_en).desc())
        ).first()
        if movimiento is None:
            return None, {}

        detalles_movimiento = list(
            session.exec(
                select(MovimientoInventarioDetalle).where(
                    MovimientoInventarioDetalle.movimiento_inventario_id == movimiento.id,
                    col(MovimientoInventarioDetalle.activo).is_(True),
                )
            ).all()
        )
        costos_por_producto: dict[UUID, Decimal] = {}
        for det in detalles_movimiento:
            if det.producto_id not in costos_por_producto:
                costos_por_producto[det.producto_id] = det.costo_unitario
        return movimiento, costos_por_producto

    def emitir_venta(
        self,
        session: Session,
        venta_id: UUID,
        *,
        usuario_auditoria: str,
        background_tasks: BackgroundTasks | None = None,
        encolar_sri: bool = False,
    ) -> Venta:
        try:
            venta = session.exec(
                select(Venta)
                .where(
                    col(Venta.id) == venta_id,
                    col(Venta.activo).is_(True),
                )
                .with_for_update()
            ).one_or_none()
            if not venta:
                raise HTTPException(status_code=404, detail="Venta no encontrada")
            ensure_entity_belongs_to_selected_company(venta.empresa_id)
            if venta.estado == EstadoVenta.EMITIDA:
                raise HTTPException(status_code=400, detail="La venta ya está emitida.")
            if venta.estado == EstadoVenta.ANULADA:
                raise HTTPException(status_code=400, detail="No se puede emitir una venta ANULADA.")
            if venta.estado != EstadoVenta.BORRADOR:
                raise HTTPException(status_code=400, detail="Solo se puede emitir una venta en estado BORRADOR.")

            self._validar_punto_venta(session, venta)

            detalles = list(
                session.exec(
                    select(VentaDetalle).where(
                        col(VentaDetalle.venta_id) == venta.id,
                        col(VentaDetalle.activo).is_(True),
                    )
                ).all()
            )
            bodega_id = self._resolver_bodega_para_emitir_venta(session, detalles)
            self._validar_stock_para_emision(session, bodega_id=bodega_id, detalles=detalles)

            movimiento_payload = MovimientoInventarioCreate(
                bodega_id=bodega_id,
                tipo_movimiento=TipoMovimientoInventario.EGRESO,
                referencia_documento=f"VENTA:{venta.id}",
                usuario_auditoria=usuario_auditoria,
                detalles=[
                    MovimientoInventarioDetalleCreate(
                        producto_id=detalle.producto_id,
                        cantidad=detalle.cantidad,
                        costo_unitario=detalle.precio_unitario,
                    )
                    for detalle in detalles
                ],
            )
            movimiento = self.movimiento_service.crear_movimiento_borrador(
                session,
                movimiento_payload,
                commit=False,
            )
            self.movimiento_service.confirmar_movimiento(
                session,
                movimiento.id,
                commit=False,
                rollback_on_error=False,
            )

            cxc_existente = session.exec(
                select(CuentaPorCobrar).where(
                    col(CuentaPorCobrar.venta_id) == venta.id,
                    col(CuentaPorCobrar.activo).is_(True),
                )
            ).one_or_none()
            if cxc_existente is not None:
                raise HTTPException(status_code=400, detail="La venta ya tiene una cuenta por cobrar activa.")

            self._asignar_secuencial_venta(session, venta, usuario_auditoria)

            total_factura = q2(venta.valor_total)
            cxc = CuentaPorCobrar(
                venta_id=venta.id,
                valor_total_factura=total_factura,
                valor_retenido=Decimal("0.00"),
                pagos_acumulados=Decimal("0.00"),
                saldo_pendiente=total_factura,
                estado=EstadoCuentaPorCobrar.PENDIENTE,
                usuario_auditoria=usuario_auditoria,
                activo=True,
            )
            session.add(cxc)

            venta.estado = EstadoVenta.EMITIDA
            venta.usuario_auditoria = usuario_auditoria
            session.add(venta)

            if encolar_sri and venta.tipo_emision == TipoEmisionVenta.ELECTRONICA:
                self.orquestador_fe_service.encolar_documento(
                    session,
                    tipo_documento=TipoDocumentoElectronico.FACTURA,
                    referencia_id=venta.id,
                    usuario_id=usuario_auditoria,
                    background_tasks=background_tasks,
                    commit=False,
                )
            session.commit()
            session.refresh(venta)
            return venta
        except Exception:
            if self._es_session_real(session):
                session.rollback()
            raise

    def anular_venta(
        self,
        session: Session,
        venta_id: UUID,
        *,
        usuario_auditoria: str,
        confirmado_portal_sri: bool = False,
        motivo: str | None = None,
    ) -> Venta:
        try:
            venta = session.exec(
                select(Venta)
                .where(
                    col(Venta.id) == venta_id,
                    col(Venta.activo).is_(True),
                )
                .with_for_update()
            ).one_or_none()
            if not venta:
                raise HTTPException(status_code=404, detail="Venta no encontrada")
            ensure_entity_belongs_to_selected_company(venta.empresa_id)
            if venta.estado == EstadoVenta.ANULADA:
                raise HTTPException(status_code=400, detail="La venta ya está ANULADA.")
            if venta.estado != EstadoVenta.EMITIDA:
                raise HTTPException(status_code=400, detail="Solo se puede anular ventas en estado EMITIDA.")

            motivo_limpio = (motivo or "").strip()
            if (
                venta.tipo_emision == TipoEmisionVenta.ELECTRONICA
                and venta.estado_sri == EstadoSriDocumento.AUTORIZADO
            ):
                if not confirmado_portal_sri:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Debe confirmar anulación previa en portal SRI "
                            "con confirmado_portal_sri=true para facturas AUTORIZADAS."
                        ),
                    )
                if not motivo_limpio:
                    raise HTTPException(
                        status_code=400,
                        detail="El motivo es obligatorio para anular una factura electrónica AUTORIZADA.",
                    )

            motivo_auditoria = motivo_limpio or "Anulación de venta"

            cxc = session.exec(
                select(CuentaPorCobrar)
                .where(
                    col(CuentaPorCobrar.venta_id) == venta.id,
                    col(CuentaPorCobrar.activo).is_(True),
                )
                .with_for_update()
            ).one_or_none()
            if cxc and (
                q2(cxc.pagos_acumulados) > Decimal("0.00")
                or q2(cxc.valor_retenido) > Decimal("0.00")
            ):
                raise ValueError("No se puede anular una venta con cobros registrados")

            detalles_venta = list(
                session.exec(
                    select(VentaDetalle).where(
                        col(VentaDetalle.venta_id) == venta.id,
                        col(VentaDetalle.activo).is_(True),
                    )
                ).all()
            )
            if not detalles_venta:
                raise HTTPException(status_code=400, detail="No se puede anular una venta sin detalles.")

            movimiento_egreso, costos_por_producto = self._obtener_egreso_inventario_venta(session, venta.id)
            if movimiento_egreso is not None:
                bodega_id = movimiento_egreso.bodega_id
            else:
                bodega_id = self._resolver_bodega_para_emitir_venta(session, detalles_venta)

            movimiento_reverso_payload = MovimientoInventarioCreate(
                bodega_id=bodega_id,
                tipo_movimiento=TipoMovimientoInventario.AJUSTE,
                referencia_documento=f"ANULACION_VENTA:{venta.id}",
                motivo_ajuste=motivo_auditoria,
                usuario_auditoria=usuario_auditoria,
                detalles=[
                    MovimientoInventarioDetalleCreate(
                        producto_id=detalle.producto_id,
                        cantidad=detalle.cantidad,
                        costo_unitario=costos_por_producto.get(detalle.producto_id, detalle.precio_unitario),
                    )
                    for detalle in detalles_venta
                ],
            )
            movimiento_reverso = self.movimiento_service.crear_movimiento_borrador(
                session,
                movimiento_reverso_payload,
                commit=False,
            )
            self.movimiento_service.confirmar_movimiento(
                session,
                movimiento_reverso.id,
                motivo_ajuste=motivo_auditoria,
                usuario_autorizador=usuario_auditoria,
                commit=False,
                rollback_on_error=False,
            )

            estado_anterior = venta.estado.value if isinstance(venta.estado, EstadoVenta) else str(venta.estado)
            venta.estado = EstadoVenta.ANULADA
            venta.usuario_auditoria = usuario_auditoria
            session.add(venta)
            session.add(
                VentaEstadoHistorial(
                    entidad_id=venta.id,
                    estado_anterior=estado_anterior,
                    estado_nuevo=EstadoVenta.ANULADA.value,
                    motivo_cambio=motivo_auditoria,
                    usuario_id=usuario_auditoria,
                )
            )

            if cxc:
                cxc.saldo_pendiente = Decimal("0.00")
                cxc.estado = EstadoCuentaPorCobrar.ANULADA
                cxc.usuario_auditoria = usuario_auditoria
                session.add(cxc)

            estado_anterior_audit = {
                "estado": estado_anterior,
                "estado_sri": venta.estado_sri.value if hasattr(venta.estado_sri, "value") else str(venta.estado_sri),
            }
            estado_nuevo_audit = {
                "estado": EstadoVenta.ANULADA.value,
                "estado_sri": venta.estado_sri.value if hasattr(venta.estado_sri, "value") else str(venta.estado_sri),
                "motivo": motivo_auditoria,
                "confirmado_portal_sri": confirmado_portal_sri,
            }
            session.add(
                AuditLog(
                    tabla_afectada=Venta.__tablename__,
                    registro_id=str(venta.id),
                    entidad=Venta.__tablename__,
                    entidad_id=venta.id,
                    accion=AuditAction.ANULAR.value,
                    estado_anterior=estado_anterior_audit,
                    estado_nuevo=estado_nuevo_audit,
                    before_json=estado_anterior_audit,
                    after_json=estado_nuevo_audit,
                    usuario_id=usuario_auditoria,
                    usuario_auditoria=usuario_auditoria,
                    created_by=usuario_auditoria,
                    updated_by=usuario_auditoria,
                )
            )

            session.commit()
            session.refresh(venta)
            return venta
        except Exception:
            if self._es_session_real(session):
                session.rollback()
            raise

    def registrar_venta(self, session: Session, payload: VentaCreate) -> Venta:
        return self.execute_create(session, payload)

    def _execute_create(
        self,
        session: Session,
        payload: VentaCreate,
        *,
        context: dict[str, Any],
        **kwargs: Any,
    ) -> Venta:
        _ = (context, kwargs)
        try:
            empresa_id, regimen_emisor, tipo_emision = self._resolver_contexto_tributario(session, payload)
            payload = payload.model_copy(
                update={
                    "empresa_id": empresa_id,
                    "regimen_emisor": regimen_emisor,
                    "tipo_emision": tipo_emision,
                }
            )
            if self._es_session_real(session):
                payload = self.medida_tributaria_service.resolve_sale(
                    session,
                    payload,
                    empresa_id=empresa_id,
                )
            empresa_id, secuencial_formateado = self._resolver_secuencial_formateado(
                session,
                payload,
                empresa_id,
            )
            empresa_scope = self._empresa_scope(empresa_id=empresa_id)
            venta = Venta(
                cliente_id=payload.cliente_id,
                empresa_id=empresa_scope or empresa_id,
                punto_emision_id=payload.punto_emision_id,
                secuencial_formateado=secuencial_formateado,
                fecha_emision=payload.fecha_emision,
                tipo_identificacion_comprador=payload.tipo_identificacion_comprador,
                identificacion_comprador=payload.identificacion_comprador,
                forma_pago=payload.forma_pago,
                regimen_emisor=regimen_emisor,
                tipo_emision=tipo_emision,
                subtotal_sin_impuestos=payload.subtotal_sin_impuestos,
                subtotal_12=payload.subtotal_12,
                subtotal_15=payload.subtotal_15,
                subtotal_8=payload.subtotal_8,
                subtotal_0=payload.subtotal_0,
                subtotal_no_objeto=payload.subtotal_no_objeto,
                monto_iva=payload.monto_iva,
                monto_ice=payload.monto_ice,
                valor_total=payload.valor_total,
                usuario_auditoria=payload.usuario_auditoria,
            )
            session.add(venta)
            session.flush()

            for detalle in payload.detalles:
                detalle_db = VentaDetalle(
                    venta_id=venta.id,
                    producto_id=detalle.producto_id,
                    descripcion=detalle.descripcion,
                    cantidad=detalle.cantidad,
                    precio_unitario=detalle.precio_unitario,
                    descuento=detalle.descuento,
                    subtotal_sin_impuesto=q2(str(detalle.model_dump()["subtotal_sin_impuesto"])),
                    es_actividad_excluida=detalle.es_actividad_excluida,
                    usuario_auditoria=payload.usuario_auditoria,
                )
                session.add(detalle_db)
                session.flush()

                for impuesto in detalle.impuestos:
                    snapshot = VentaDetalleImpuesto(
                        venta_detalle_id=detalle_db.id,
                        tipo_impuesto=impuesto.tipo_impuesto,
                        codigo_impuesto_sri=impuesto.codigo_impuesto_sri,
                        codigo_porcentaje_sri=impuesto.codigo_porcentaje_sri,
                        componente=impuesto.componente,
                        unidad_gravable=impuesto.unidad_gravable,
                        cantidad_gravable=(
                            detalle.base_imponible_impuesto(impuesto)
                            if impuesto.componente.value == "ESPECIFICO"
                            else None
                        ),
                        medida_temporal_id=impuesto.medida_temporal_id,
                        referencia_legal_temporal=impuesto.referencia_legal_temporal,
                        tarifa=impuesto.tarifa,
                        base_imponible=detalle.base_imponible_impuesto(impuesto),
                        valor_impuesto=detalle.valor_impuesto(impuesto),
                        usuario_auditoria=payload.usuario_auditoria,
                    )
                    session.add(snapshot)

            session.commit()
            session.refresh(venta)
            return venta
        except Exception:
            if self._es_session_real(session):
                session.rollback()
            raise

    def registrar_venta_desde_productos(self, session: Session, payload: VentaRegistroCreate) -> Venta:
        venta_create = self.hidratar_venta_desde_productos(session, payload)
        return self.registrar_venta(session, venta_create)

    def actualizar_venta(self, session: Session, venta_id: UUID, payload: VentaUpdate) -> Venta:
        venta = session.get(Venta, venta_id)
        if not venta or not venta.activo:
            raise HTTPException(status_code=404, detail="Venta no encontrada")
        ensure_entity_belongs_to_selected_company(venta.empresa_id)
        if venta.estado == EstadoVenta.EMITIDA:
            raise HTTPException(status_code=400, detail="No se puede editar una venta en estado EMITIDA.")

        if payload.tipo_identificacion_comprador is not None:
            venta.tipo_identificacion_comprador = payload.tipo_identificacion_comprador
        if payload.identificacion_comprador is not None:
            venta.identificacion_comprador = payload.identificacion_comprador
        if payload.forma_pago is not None:
            venta.forma_pago = payload.forma_pago
        if payload.tipo_emision is not None:
            if (
                payload.tipo_emision == TipoEmisionVenta.NOTA_VENTA_FISICA
                and venta.regimen_emisor != RegimenTributario.RIMPE_NEGOCIO_POPULAR
            ):
                raise HTTPException(
                    status_code=400,
                    detail="NOTA_VENTA_FISICA solo está permitido para régimen RIMPE_NEGOCIO_POPULAR.",
                )
            venta.tipo_emision = payload.tipo_emision

        venta.usuario_auditoria = payload.usuario_auditoria
        session.add(venta)
        session.commit()
        session.refresh(venta)
        return venta

    def obtener_venta_read(self, session: Session, venta_id: UUID) -> VentaRead:
        from collections import defaultdict

        venta = session.get(Venta, venta_id)
        if not venta or not venta.activo:
            raise HTTPException(status_code=404, detail="Venta no encontrada")
        ensure_entity_belongs_to_selected_company(venta.empresa_id)

        stmt_detalle = select(VentaDetalle).where(
            col(VentaDetalle.venta_id) == venta.id,
            col(VentaDetalle.activo).is_(True),
        )
        detalles_db = list(session.exec(stmt_detalle).all())
        detalle_ids = [detalle.id for detalle in detalles_db]

        impuestos_por_detalle: dict[UUID, list[VentaDetalleImpuesto]] = defaultdict(list)
        if detalle_ids:
            impuestos_db = list(
                session.exec(
                    select(VentaDetalleImpuesto).where(
                        col(VentaDetalleImpuesto.venta_detalle_id).in_(detalle_ids),
                        col(VentaDetalleImpuesto.activo).is_(True),
                    )
                ).all()
            )
            for impuesto in impuestos_db:
                impuestos_por_detalle[impuesto.venta_detalle_id].append(impuesto)

        detalles_read: list[VentaDetalleRead] = []
        for detalle in detalles_db:
            impuestos_read = [
                VentaDetalleImpuestoRead(
                    tipo_impuesto=imp.tipo_impuesto,
                    codigo_impuesto_sri=imp.codigo_impuesto_sri,
                    codigo_porcentaje_sri=imp.codigo_porcentaje_sri,
                    componente=imp.componente,
                    unidad_gravable=imp.unidad_gravable,
                    cantidad_gravable=imp.cantidad_gravable,
                    medida_temporal_id=imp.medida_temporal_id,
                    referencia_legal_temporal=imp.referencia_legal_temporal,
                    tarifa=imp.tarifa,
                    base_imponible=imp.base_imponible,
                    valor_impuesto=imp.valor_impuesto,
                )
                for imp in impuestos_por_detalle.get(detalle.id, [])
            ]

            detalles_read.append(
                VentaDetalleRead(
                    producto_id=detalle.producto_id,
                    descripcion=detalle.descripcion,
                    cantidad=detalle.cantidad,
                    precio_unitario=detalle.precio_unitario,
                    descuento=detalle.descuento,
                    subtotal_sin_impuesto=detalle.subtotal_sin_impuesto,
                    es_actividad_excluida=detalle.es_actividad_excluida,
                    impuestos=impuestos_read,
                )
            )

        return VentaRead(
            id=venta.id,
            cliente_id=venta.cliente_id,
            empresa_id=venta.empresa_id,
            punto_emision_id=venta.punto_emision_id,
            secuencial_formateado=venta.secuencial_formateado,
            fecha_emision=venta.fecha_emision,
            tipo_identificacion_comprador=venta.tipo_identificacion_comprador,
            identificacion_comprador=venta.identificacion_comprador,
            forma_pago=venta.forma_pago,
            tipo_emision=venta.tipo_emision,
            regimen_emisor=venta.regimen_emisor,
            estado=venta.estado,
            estado_sri=venta.estado_sri,
            sri_intentos=venta.sri_intentos,
            sri_ultimo_error=venta.sri_ultimo_error,
            subtotal_sin_impuestos=venta.subtotal_sin_impuestos,
            subtotal_12=venta.subtotal_12,
            subtotal_15=venta.subtotal_15,
            subtotal_8=venta.subtotal_8,
            subtotal_0=venta.subtotal_0,
            subtotal_no_objeto=venta.subtotal_no_objeto,
            monto_iva=venta.monto_iva,
            monto_ice=venta.monto_ice,
            valor_total=venta.valor_total,
            total=venta.valor_total,
            detalles=detalles_read,
            creado_en=venta.creado_en,
            actualizado_en=venta.actualizado_en,
        )

    def listar_ventas(
        self,
        session: Session,
        *,
        limit: int,
        offset: int,
        only_active: bool = True,
        fecha_inicio: date | None = None,
        fecha_fin: date | None = None,
        estado: EstadoVenta | None = None,
        tipo_emision: TipoEmisionVenta | None = None,
        texto: str | None = None,
    ) -> tuple[list[dict[str, Any]], PaginationMeta]:
        stmt = select(Venta)
        empresa_scope = self._empresa_scope()
        if empresa_scope is not None:
            stmt = stmt.where(Venta.empresa_id == empresa_scope)
        if only_active:
            stmt = stmt.where(col(Venta.activo).is_(True))
        else:
            stmt = stmt.execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        if fecha_inicio is not None:
            stmt = stmt.where(Venta.fecha_emision >= fecha_inicio)
        if fecha_fin is not None:
            stmt = stmt.where(Venta.fecha_emision <= fecha_fin)
        if estado is not None:
            stmt = stmt.where(Venta.estado == estado)
        if tipo_emision is not None:
            stmt = stmt.where(Venta.tipo_emision == tipo_emision)
        if texto:
            pattern = f"%{texto.strip()}%"
            stmt = stmt.where(
                or_(
                    col(Venta.identificacion_comprador).ilike(pattern),
                    col(Venta.secuencial_formateado).ilike(pattern),
                )
            )

        total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
        ventas = list(
            session.exec(
                stmt.order_by(col(Venta.fecha_emision).desc(), col(Venta.creado_en).desc())
                .offset(offset)
                .limit(limit)
            ).all()
        )

        items = [
            {
                "id": venta.id,
                "fecha_emision": venta.fecha_emision,
                "cliente_id": venta.cliente_id,
                "cliente": venta.identificacion_comprador,
                "numero_factura": venta.secuencial_formateado,
                "valor_total": venta.valor_total,
                "estado": venta.estado,
                "estado_sri": venta.estado_sri,
                "tipo_emision": venta.tipo_emision,
            }
            for venta in ventas
        ]
        return items, build_pagination_meta(total=total, limit=limit, offset=offset)
