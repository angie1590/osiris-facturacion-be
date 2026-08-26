from __future__ import annotations

from sqlalchemy import func
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, select

from osiris.core.company_scope import ensure_entity_belongs_to_selected_company, resolve_company_scope
from osiris.modules.sri.core_sri.models import (
    CuentaPorCobrar,
    EstadoCuentaPorCobrar,
    EstadoRetencionRecibida,
    RetencionRecibida,
    RetencionRecibidaEstadoHistorial,
    RetencionRecibidaDetalle,
    Venta,
)
from osiris.modules.ventas.services.cxc_service import CuentaPorCobrarService
from osiris.modules.sri.core_sri.all_schemas import (
    RetencionRecibidaCreate,
    RetencionRecibidaDetalleRead,
    RetencionRecibidaListItemRead,
    RetencionRecibidaRead,
)
from osiris.modules.ventas.strategies.validacion_impuestos_sri_strategy import ValidacionImpuestosSRIStrategy
from osiris.utils.pagination import build_pagination_meta
from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION


class RetencionRecibidaService:
    def __init__(self, validacion_impuestos_strategy: ValidacionImpuestosSRIStrategy | None = None) -> None:
        self.cxc_service = CuentaPorCobrarService()
        self.validacion_impuestos_strategy = validacion_impuestos_strategy or ValidacionImpuestosSRIStrategy()

    def _validar_venta(self, session: Session, venta_id: UUID) -> Venta:
        venta = session.get(Venta, venta_id)
        if not venta or not venta.activo:
            raise HTTPException(status_code=404, detail="Venta no encontrada para registrar retencion recibida.")
        ensure_entity_belongs_to_selected_company(venta.empresa_id)
        return venta

    @staticmethod
    def _empresa_scope() -> UUID | None:
        return resolve_company_scope()

    def _validar_unicidad(self, session: Session, cliente_id: UUID, numero_retencion: str) -> None:
        existente = session.exec(
            select(RetencionRecibida).where(
                RetencionRecibida.cliente_id == cliente_id,
                RetencionRecibida.numero_retencion == numero_retencion,
                RetencionRecibida.activo.is_(True),
            )
        ).first()
        if existente:
            raise HTTPException(
                status_code=400,
                detail="Ya existe una retencion recibida con ese numero para el cliente.",
            )

    def crear_retencion_recibida(
        self,
        session: Session,
        payload: RetencionRecibidaCreate,
    ) -> RetencionRecibidaRead:
        venta = self._validar_venta(session, payload.venta_id)
        self._validar_unicidad(session, payload.cliente_id, payload.numero_retencion)
        try:
            payload = self.validacion_impuestos_strategy.validar_retencion_recibida(payload, venta)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        retencion = RetencionRecibida(
            venta_id=payload.venta_id,
            cliente_id=payload.cliente_id,
            numero_retencion=payload.numero_retencion,
            clave_acceso_sri=payload.clave_acceso_sri,
            fecha_emision=payload.fecha_emision,
            estado=payload.estado,
            total_retenido=payload.total_retenido,
            usuario_auditoria=payload.usuario_auditoria,
            activo=True,
        )
        session.add(retencion)
        session.flush()

        for detalle in payload.detalles:
            session.add(
                RetencionRecibidaDetalle(
                    retencion_recibida_id=retencion.id,
                    codigo_impuesto_sri=detalle.codigo_impuesto_sri,
                    porcentaje_aplicado=detalle.porcentaje_aplicado,
                    base_imponible=detalle.base_imponible,
                    valor_retenido=detalle.valor_retenido,
                    usuario_auditoria=payload.usuario_auditoria,
                    activo=True,
                )
            )

        session.commit()
        return self.obtener_retencion_recibida_read(session, retencion.id)

    def aplicar_retencion_recibida(self, session: Session, retencion_id: UUID) -> RetencionRecibidaRead:
        try:
            retencion = session.exec(
                select(RetencionRecibida)
                .where(
                    RetencionRecibida.id == retencion_id,
                    RetencionRecibida.activo.is_(True),
                )
                .with_for_update()
            ).one_or_none()
            if not retencion:
                raise HTTPException(status_code=404, detail="Retencion recibida no encontrada")
            self._validar_venta(session, retencion.venta_id)
            if retencion.estado != EstadoRetencionRecibida.BORRADOR:
                raise HTTPException(
                    status_code=400,
                    detail="Solo se puede aplicar una retencion recibida en estado BORRADOR.",
                )

            cxc = session.exec(
                select(CuentaPorCobrar)
                .where(
                    CuentaPorCobrar.venta_id == retencion.venta_id,
                    CuentaPorCobrar.activo.is_(True),
                )
                .with_for_update()
            ).one_or_none()
            if not cxc:
                raise HTTPException(status_code=404, detail="Cuenta por cobrar no encontrada para la venta")
            if cxc.estado == EstadoCuentaPorCobrar.ANULADA:
                raise HTTPException(status_code=400, detail="No se puede aplicar retencion sobre una CxC ANULADA.")

            self.cxc_service.aplicar_retencion_en_cxc(cxc, retencion.total_retenido)
            session.add(cxc)

            retencion.estado = EstadoRetencionRecibida.APLICADA
            session.add(retencion)

            session.commit()
            return self.obtener_retencion_recibida_read(session, retencion.id)
        except Exception:
            session.rollback()
            raise

    def anular_retencion_recibida(
        self,
        session: Session,
        retencion_id: UUID,
        *,
        motivo: str,
        usuario_auditoria: str,
    ) -> RetencionRecibidaRead:
        try:
            motivo_limpio = (motivo or "").strip()
            if not motivo_limpio:
                raise HTTPException(status_code=400, detail="El motivo de anulación es obligatorio.")

            retencion = session.exec(
                select(RetencionRecibida)
                .where(
                    RetencionRecibida.id == retencion_id,
                    RetencionRecibida.activo.is_(True),
                )
                .with_for_update()
            ).one_or_none()
            if not retencion:
                raise HTTPException(status_code=404, detail="Retencion recibida no encontrada")
            self._validar_venta(session, retencion.venta_id)
            if retencion.estado != EstadoRetencionRecibida.APLICADA:
                raise HTTPException(
                    status_code=400,
                    detail="Solo se puede anular una retencion recibida en estado APLICADA.",
                )

            cxc = session.exec(
                select(CuentaPorCobrar)
                .where(
                    CuentaPorCobrar.venta_id == retencion.venta_id,
                    CuentaPorCobrar.activo.is_(True),
                )
                .with_for_update()
            ).one_or_none()
            if not cxc:
                raise HTTPException(status_code=404, detail="Cuenta por cobrar no encontrada para la venta")
            if cxc.estado == EstadoCuentaPorCobrar.ANULADA:
                raise HTTPException(status_code=400, detail="No se puede anular en una CxC ANULADA.")

            self.cxc_service.revertir_retencion_en_cxc(cxc, retencion.total_retenido)
            session.add(cxc)

            estado_anterior = retencion.estado
            retencion.estado = EstadoRetencionRecibida.ANULADA
            retencion.usuario_auditoria = usuario_auditoria
            session.add(retencion)
            session.add(
                RetencionRecibidaEstadoHistorial(
                    entidad_id=retencion.id,
                    estado_anterior=estado_anterior.value,
                    estado_nuevo=EstadoRetencionRecibida.ANULADA.value,
                    motivo_cambio=motivo_limpio,
                    usuario_id=usuario_auditoria,
                )
            )

            session.commit()
            return self.obtener_retencion_recibida_read(session, retencion.id)
        except Exception:
            session.rollback()
            raise

    def obtener_retencion_recibida_read(
        self,
        session: Session,
        retencion_recibida_id: UUID,
    ) -> RetencionRecibidaRead:
        retencion = session.get(RetencionRecibida, retencion_recibida_id)
        if not retencion or not retencion.activo:
            raise HTTPException(status_code=404, detail="Retencion recibida no encontrada")
        self._validar_venta(session, retencion.venta_id)

        detalles = list(
            session.exec(
                select(RetencionRecibidaDetalle).where(
                    RetencionRecibidaDetalle.retencion_recibida_id == retencion.id,
                    RetencionRecibidaDetalle.activo.is_(True),
                )
            ).all()
        )

        return RetencionRecibidaRead(
            id=retencion.id,
            venta_id=retencion.venta_id,
            cliente_id=retencion.cliente_id,
            numero_retencion=retencion.numero_retencion,
            clave_acceso_sri=retencion.clave_acceso_sri,
            fecha_emision=retencion.fecha_emision,
            estado=retencion.estado,
            total_retenido=retencion.total_retenido,
            detalles=[
                RetencionRecibidaDetalleRead.model_validate(detalle, from_attributes=True)
                for detalle in detalles
            ],
        )

    def listar_retenciones_recibidas(
        self,
        session: Session,
        *,
        limit: int,
        offset: int,
        only_active: bool = True,
        fecha_inicio=None,
        fecha_fin=None,
        estado: EstadoRetencionRecibida | None = None,
    ):
        stmt = select(RetencionRecibida)
        empresa_scope = self._empresa_scope()
        if empresa_scope is not None:
            stmt = stmt.join(Venta, Venta.id == RetencionRecibida.venta_id).where(
                Venta.activo.is_(True),
                Venta.empresa_id == empresa_scope,
            )
        if only_active:
            stmt = stmt.where(RetencionRecibida.activo.is_(True))
        else:
            stmt = stmt.execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        if fecha_inicio is not None:
            stmt = stmt.where(RetencionRecibida.fecha_emision >= fecha_inicio)
        if fecha_fin is not None:
            stmt = stmt.where(RetencionRecibida.fecha_emision <= fecha_fin)
        if estado is not None:
            stmt = stmt.where(RetencionRecibida.estado == estado)

        total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
        retenciones = list(
            session.exec(
                stmt.order_by(RetencionRecibida.fecha_emision.desc(), RetencionRecibida.creado_en.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        )
        items = [
            RetencionRecibidaListItemRead(
                id=retencion.id,
                venta_id=retencion.venta_id,
                cliente_id=retencion.cliente_id,
                numero_retencion=retencion.numero_retencion,
                fecha_emision=retencion.fecha_emision,
                estado=retencion.estado,
                total_retenido=retencion.total_retenido,
            )
            for retencion in retenciones
        ]
        return items, build_pagination_meta(total=total, limit=limit, offset=offset)
