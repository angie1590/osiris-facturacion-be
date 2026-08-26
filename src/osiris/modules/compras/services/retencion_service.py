from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import BackgroundTasks, HTTPException
from sqlmodel import Session, select

from osiris.core.company_scope import resolve_company_scope
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.sri.core_sri.models import (
    Compra,
    CuentaPorPagar,
    EstadoCuentaPorPagar,
    EstadoRetencion,
    PlantillaRetencion,
    PlantillaRetencionDetalle,
    Retencion,
    RetencionDetalle,
    TipoDocumentoElectronico,
    TipoRetencionSRI,
)
from osiris.modules.sri.facturacion_electronica.services.fe_mapper_service import FEMapperService
from osiris.modules.sri.facturacion_electronica.services.orquestador_fe_service import OrquestadorFEService
from osiris.modules.sri.core_sri.all_schemas import (
    GuardarPlantillaRetencionRequest,
    PlantillaRetencionDetalleRead,
    PlantillaRetencionRead,
    RetencionCreate,
    RetencionDetalleRead,
    RetencionEmitRequest,
    RetencionRead,
    RetencionSugeridaDetalleRead,
    RetencionSugeridaRead,
    q2,
)
from osiris.modules.sri.facturacion_electronica.services.sri_async_service import SriAsyncService
from osiris.modules.compras.strategies.validacion_impuestos_sri_strategy import ValidacionImpuestosSRIStrategy


class RetencionService:
    def __init__(self) -> None:
        self.fe_mapper_service = FEMapperService()
        self.sri_async_service = SriAsyncService()
        self.validacion_impuestos_strategy = ValidacionImpuestosSRIStrategy()
        self.orquestador_fe_service = OrquestadorFEService(retencion_sri_service=self.sri_async_service)

    @staticmethod
    def _empresa_scope() -> UUID | None:
        return resolve_company_scope()

    def _validar_compra_scope(self, session: Session, compra: Compra) -> None:
        empresa_scope = self._empresa_scope()
        if empresa_scope is None:
            return
        if compra.sucursal_id is None:
            raise HTTPException(status_code=403, detail="No autorizado para operar compras de otra empresa.")
        sucursal = session.get(Sucursal, compra.sucursal_id)
        if not sucursal or not sucursal.activo or sucursal.empresa_id != empresa_scope:
            raise HTTPException(status_code=403, detail="No autorizado para operar compras de otra empresa.")

    def _obtener_compra(self, session: Session, compra_id: UUID) -> Compra:
        compra = session.get(Compra, compra_id)
        if not compra or not compra.activo:
            raise HTTPException(status_code=404, detail="Compra no encontrada")
        self._validar_compra_scope(session, compra)
        return compra

    def _obtener_plantilla_para_proveedor(
        self,
        session: Session,
        proveedor_id: UUID,
    ) -> PlantillaRetencion | None:
        stmt = (
            select(PlantillaRetencion)
            .where(
                PlantillaRetencion.activo.is_(True),
                PlantillaRetencion.proveedor_id == proveedor_id,
            )
            .order_by(PlantillaRetencion.actualizado_en.desc())
        )
        plantilla = session.exec(stmt).first()
        if plantilla:
            return plantilla

        stmt_global = (
            select(PlantillaRetencion)
            .where(
                PlantillaRetencion.activo.is_(True),
                PlantillaRetencion.es_global.is_(True),
            )
            .order_by(PlantillaRetencion.actualizado_en.desc())
        )
        return session.exec(stmt_global).first()

    def _obtener_detalles_plantilla(
        self,
        session: Session,
        plantilla_id: UUID,
    ) -> list[PlantillaRetencionDetalle]:
        stmt = (
            select(PlantillaRetencionDetalle)
            .where(
                PlantillaRetencionDetalle.activo.is_(True),
                PlantillaRetencionDetalle.plantilla_retencion_id == plantilla_id,
            )
            .order_by(PlantillaRetencionDetalle.creado_en.asc())
        )
        return list(session.exec(stmt).all())

    def _obtener_retencion(self, session: Session, retencion_id: UUID) -> Retencion:
        retencion = session.get(Retencion, retencion_id)
        if not retencion or not retencion.activo:
            raise HTTPException(status_code=404, detail="Retencion no encontrada")
        self._obtener_compra(session, retencion.compra_id)
        return retencion

    def _obtener_detalles_retencion(self, session: Session, retencion_id: UUID) -> list[RetencionDetalle]:
        stmt = (
            select(RetencionDetalle)
            .where(
                RetencionDetalle.activo.is_(True),
                RetencionDetalle.retencion_id == retencion_id,
            )
            .order_by(RetencionDetalle.creado_en.asc())
        )
        return list(session.exec(stmt).all())

    def _obtener_cxp_bloqueada_por_compra(self, session: Session, compra_id: UUID) -> CuentaPorPagar:
        self._obtener_compra(session, compra_id)
        cxp = session.exec(
            select(CuentaPorPagar)
            .where(
                CuentaPorPagar.compra_id == compra_id,
                CuentaPorPagar.activo.is_(True),
            )
            .with_for_update()
        ).one_or_none()
        if not cxp:
            raise HTTPException(status_code=404, detail="Cuenta por pagar no encontrada para la compra.")
        return cxp

    @staticmethod
    def _actualizar_estado_cxp(cxp: CuentaPorPagar) -> None:
        nuevo_saldo = q2(cxp.valor_total_factura - cxp.valor_retenido - cxp.pagos_acumulados)
        if nuevo_saldo < Decimal("0.00"):
            raise HTTPException(
                status_code=400,
                detail="La retencion excede el saldo disponible de la cuenta por pagar.",
            )
        cxp.saldo_pendiente = nuevo_saldo
        if nuevo_saldo == Decimal("0.00"):
            cxp.estado = EstadoCuentaPorPagar.PAGADA
        elif cxp.valor_retenido > Decimal("0.00") or cxp.pagos_acumulados > Decimal("0.00"):
            cxp.estado = EstadoCuentaPorPagar.PARCIAL
        else:
            cxp.estado = EstadoCuentaPorPagar.PENDIENTE

    def _validar_no_duplicidad_retencion_por_compra(self, session: Session, compra_id: UUID) -> None:
        existente = session.exec(
            select(Retencion).where(
                Retencion.compra_id == compra_id,
                Retencion.activo.is_(True),
                Retencion.estado != EstadoRetencion.ANULADA,
            )
        ).first()
        if existente:
            raise HTTPException(
                status_code=400,
                detail="Ya existe una retencion activa asociada a esta compra.",
            )

    def sugerir_retencion(self, session: Session, compra_id: UUID) -> RetencionSugeridaRead:
        compra = self._obtener_compra(session, compra_id)
        plantilla = self._obtener_plantilla_para_proveedor(session, compra.proveedor_id)
        if not plantilla:
            raise HTTPException(
                status_code=404,
                detail="No existe plantilla de retencion para el proveedor ni plantilla global.",
            )

        detalles_plantilla = self._obtener_detalles_plantilla(session, plantilla.id)
        if not detalles_plantilla:
            raise HTTPException(status_code=400, detail="La plantilla de retencion no tiene detalles.")

        sugeridos: list[RetencionSugeridaDetalleRead] = []
        total_retenido = Decimal("0.00")
        for detalle in detalles_plantilla:
            base = (
                self.validacion_impuestos_strategy.base_retencion_iva(compra)
                if detalle.tipo == TipoRetencionSRI.IVA
                else self.validacion_impuestos_strategy.base_retencion_renta(compra)
            )
            valor = q2(base * q2(detalle.porcentaje) / Decimal("100"))
            sugeridos.append(
                RetencionSugeridaDetalleRead(
                    codigo_retencion_sri=detalle.codigo_retencion_sri,
                    tipo=detalle.tipo,
                    porcentaje=q2(detalle.porcentaje),
                    base_calculo=base,
                    valor_retenido=valor,
                )
            )
            total_retenido += valor

        return RetencionSugeridaRead(
            compra_id=compra.id,
            plantilla_id=plantilla.id,
            proveedor_id=plantilla.proveedor_id,
            detalles=sugeridos,
            total_retenido=q2(total_retenido),
        )

    def crear_retencion(
        self,
        session: Session,
        compra_id: UUID,
        payload: RetencionCreate,
        *,
        encolar_sri: bool = False,
        background_tasks: BackgroundTasks | None = None,
        commit: bool = True,
        rollback_on_error: bool = True,
    ) -> RetencionRead:
        try:
            self._obtener_compra(session, compra_id)
            self._validar_no_duplicidad_retencion_por_compra(session, compra_id)

            retencion = Retencion(
                compra_id=compra_id,
                fecha_emision=payload.fecha_emision,
                estado=EstadoRetencion.REGISTRADA,
                total_retenido=payload.total_retenido,
                usuario_auditoria=payload.usuario_auditoria,
                activo=True,
            )
            session.add(retencion)
            session.flush()

            for detalle in payload.detalles:
                session.add(
                    RetencionDetalle(
                        retencion_id=retencion.id,
                        codigo_retencion_sri=detalle.codigo_retencion_sri,
                        tipo=detalle.tipo,
                        porcentaje=q2(detalle.porcentaje),
                        base_calculo=q2(detalle.base_calculo),
                        valor_retenido=detalle.valor_retenido,
                        usuario_auditoria=payload.usuario_auditoria,
                        activo=True,
                    )
                )

            if commit:
                session.commit()
            else:
                session.flush()
            if encolar_sri:
                return self.emitir_retencion(
                    session,
                    retencion.id,
                    RetencionEmitRequest(
                        usuario_auditoria=payload.usuario_auditoria,
                        encolar=True,
                    ),
                    background_tasks=background_tasks,
                    commit=commit,
                    rollback_on_error=rollback_on_error,
                )
            return self.obtener_retencion_read(session, retencion.id)
        except Exception:
            if rollback_on_error:
                session.rollback()
            raise

    def emitir_retencion(
        self,
        session: Session,
        retencion_id: UUID,
        payload: RetencionEmitRequest,
        *,
        background_tasks: BackgroundTasks | None = None,
        commit: bool = True,
        rollback_on_error: bool = True,
    ) -> RetencionRead:
        try:
            retencion = self._obtener_retencion(session, retencion_id)
            if retencion.estado == EstadoRetencion.ANULADA:
                raise HTTPException(status_code=400, detail="No se puede emitir una retencion ANULADA.")
            if retencion.estado in {EstadoRetencion.EMITIDA, EstadoRetencion.ENCOLADA}:
                return self.obtener_retencion_read(session, retencion.id)

            cxp = self._obtener_cxp_bloqueada_por_compra(session, retencion.compra_id)
            cxp.valor_retenido = q2(cxp.valor_retenido + retencion.total_retenido)
            self._actualizar_estado_cxp(cxp)
            cxp.usuario_auditoria = payload.usuario_auditoria
            session.add(cxp)

            retencion.estado = EstadoRetencion.ENCOLADA if payload.encolar else EstadoRetencion.EMITIDA
            retencion.usuario_auditoria = payload.usuario_auditoria
            session.add(retencion)

            if payload.encolar:
                self.orquestador_fe_service.encolar_documento(
                    session,
                    tipo_documento=TipoDocumentoElectronico.RETENCION,
                    referencia_id=retencion.id,
                    usuario_id=payload.usuario_auditoria,
                    background_tasks=background_tasks,
                    commit=False,
                )

            if commit:
                session.commit()
            else:
                session.flush()
            return self.obtener_retencion_read(session, retencion.id)
        except Exception:
            if rollback_on_error:
                session.rollback()
            raise

    def obtener_retencion_read(self, session: Session, retencion_id: UUID) -> RetencionRead:
        retencion = self._obtener_retencion(session, retencion_id)
        detalles = self._obtener_detalles_retencion(session, retencion.id)
        return RetencionRead(
            id=retencion.id,
            compra_id=retencion.compra_id,
            fecha_emision=retencion.fecha_emision,
            estado=retencion.estado,
            estado_sri=retencion.estado_sri,
            sri_intentos=retencion.sri_intentos,
            sri_ultimo_error=retencion.sri_ultimo_error,
            total_retenido=retencion.total_retenido,
            detalles=[
                RetencionDetalleRead.model_validate(detalle, from_attributes=True) for detalle in detalles
            ],
        )

    def obtener_payload_fe_retencion(self, session: Session, retencion_id: UUID) -> dict:
        retencion = self.obtener_retencion_read(session, retencion_id)
        return self.fe_mapper_service.retencion_to_fe_payload(retencion)

    def guardar_plantilla_desde_retencion_digitada(
        self,
        session: Session,
        compra_id: UUID,
        payload: GuardarPlantillaRetencionRequest,
    ) -> PlantillaRetencionRead:
        compra = self._obtener_compra(session, compra_id)
        proveedor_id = None if payload.es_global else compra.proveedor_id

        if not payload.es_global:
            prev_stmt = select(PlantillaRetencion).where(
                PlantillaRetencion.activo.is_(True),
                PlantillaRetencion.proveedor_id == compra.proveedor_id,
            )
        else:
            prev_stmt = select(PlantillaRetencion).where(
                PlantillaRetencion.activo.is_(True),
                PlantillaRetencion.es_global.is_(True),
            )
        previas = list(session.exec(prev_stmt).all())
        for previa in previas:
            previa.activo = False
            previa.usuario_auditoria = payload.usuario_auditoria
            session.add(previa)

        plantilla = PlantillaRetencion(
            proveedor_id=proveedor_id,
            nombre=payload.nombre,
            es_global=payload.es_global,
            usuario_auditoria=payload.usuario_auditoria,
            activo=True,
        )
        session.add(plantilla)
        session.flush()

        for detalle in payload.detalles:
            session.add(
                PlantillaRetencionDetalle(
                    plantilla_retencion_id=plantilla.id,
                    codigo_retencion_sri=detalle.codigo_retencion_sri,
                    tipo=detalle.tipo,
                    porcentaje=q2(detalle.porcentaje),
                    usuario_auditoria=payload.usuario_auditoria,
                    activo=True,
                )
            )

        session.commit()
        return self.obtener_plantilla_read(session, plantilla.id)

    def obtener_plantilla_read(self, session: Session, plantilla_id: UUID) -> PlantillaRetencionRead:
        plantilla = session.get(PlantillaRetencion, plantilla_id)
        if not plantilla or not plantilla.activo:
            raise HTTPException(status_code=404, detail="Plantilla de retencion no encontrada")
        detalles = self._obtener_detalles_plantilla(session, plantilla.id)
        return PlantillaRetencionRead(
            id=plantilla.id,
            proveedor_id=plantilla.proveedor_id,
            nombre=plantilla.nombre,
            es_global=plantilla.es_global,
            detalles=[
                PlantillaRetencionDetalleRead.model_validate(detalle, from_attributes=True)
                for detalle in detalles
            ],
        )
