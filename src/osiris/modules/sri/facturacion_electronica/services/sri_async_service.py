from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from typing import Callable, Protocol
from uuid import UUID

from fastapi import BackgroundTasks, HTTPException
from sqlmodel import Session, select

from osiris.core.db import engine as default_engine
from osiris.modules.sri.core_sri.models import (
    DocumentoSriCola,
    EstadoColaSri,
    EstadoRetencion,
    EstadoSriDocumento,
    Retencion,
    RetencionDetalle,
    RetencionEstadoHistorial,
)
from osiris.modules.sri.facturacion_electronica.services.fe_mapper_service import FEMapperService
from osiris.modules.sri.core_sri.all_schemas import RetencionDetalleRead, RetencionRead


class FEECOrquestadorGateway(Protocol):
    def enviar_documento(self, *, tipo_documento: str, payload: dict) -> dict:
        ...


class FEECOrquestadorGatewayDefault:
    def enviar_documento(self, *, tipo_documento: str, payload: dict) -> dict:
        _ = (tipo_documento, payload)
        return {"estado": "AUTORIZADO", "mensaje": "Autorizado por orquestador FE-EC"}


class SriAsyncService:
    def __init__(self, gateway: FEECOrquestadorGateway | None = None, db_engine=None) -> None:
        self.gateway = gateway or FEECOrquestadorGatewayDefault()
        self.fe_mapper = FEMapperService()
        self.db_engine = db_engine or default_engine

    def _retencion_read(self, session: Session, retencion_id: UUID) -> RetencionRead:
        retencion = session.get(Retencion, retencion_id)
        if not retencion or not retencion.activo:
            raise HTTPException(status_code=404, detail="Retencion no encontrada para envio SRI")
        detalles = list(
            session.exec(
                select(RetencionDetalle)
                .where(
                    RetencionDetalle.retencion_id == retencion.id,
                    RetencionDetalle.activo.is_(True),
                )
                .order_by(RetencionDetalle.creado_en.asc())
            ).all()
        )
        return RetencionRead(
            id=retencion.id,
            compra_id=retencion.compra_id,
            fecha_emision=retencion.fecha_emision,
            estado=retencion.estado,
            estado_sri=retencion.estado_sri,
            sri_intentos=retencion.sri_intentos,
            sri_ultimo_error=retencion.sri_ultimo_error,
            total_retenido=retencion.total_retenido,
            detalles=[RetencionDetalleRead.model_validate(d, from_attributes=True) for d in detalles],
        )

    @staticmethod
    def _historial(
        session: Session,
        *,
        retencion: Retencion,
        estado_anterior: str,
        estado_nuevo: str,
        motivo: str,
        usuario_id: str | None,
    ) -> None:
        session.add(
            RetencionEstadoHistorial(
                entidad_id=retencion.id,
                estado_anterior=estado_anterior,
                estado_nuevo=estado_nuevo,
                motivo_cambio=motivo,
                usuario_id=usuario_id,
            )
        )

    def encolar_retencion(
        self,
        session: Session,
        *,
        retencion_id: UUID,
        usuario_id: str | None,
        background_tasks: BackgroundTasks | None = None,
        commit: bool = True,
    ) -> DocumentoSriCola:
        retencion = session.get(Retencion, retencion_id)
        if not retencion or not retencion.activo:
            raise HTTPException(status_code=404, detail="Retencion no encontrada")

        existente = session.exec(
            select(DocumentoSriCola).where(
                DocumentoSriCola.entidad_id == retencion.id,
                DocumentoSriCola.tipo_documento == "RETENCION",
                DocumentoSriCola.activo.is_(True),
                DocumentoSriCola.estado.in_(
                    [
                        EstadoColaSri.PENDIENTE,
                        EstadoColaSri.PROCESANDO,
                        EstadoColaSri.REINTENTO_PROGRAMADO,
                    ]
                ),
            )
        ).first()
        if existente:
            if background_tasks:
                background_tasks.add_task(self.procesar_documento_sri, existente.id)
            return existente

        payload = self.fe_mapper.retencion_to_fe_payload(self._retencion_read(session, retencion.id))
        tarea = DocumentoSriCola(
            entidad_id=retencion.id,
            tipo_documento="RETENCION",
            estado=EstadoColaSri.PENDIENTE,
            intentos_realizados=0,
            max_intentos=3,
            payload_json=json.dumps(payload, ensure_ascii=False),
            usuario_auditoria=usuario_id,
            activo=True,
        )
        session.add(tarea)

        estado_anterior = retencion.estado_sri.value
        retencion.estado_sri = EstadoSriDocumento.PENDIENTE
        retencion.sri_ultimo_error = None
        retencion.usuario_auditoria = usuario_id
        session.add(retencion)
        self._historial(
            session,
            retencion=retencion,
            estado_anterior=estado_anterior,
            estado_nuevo=EstadoSriDocumento.PENDIENTE.value,
            motivo="Documento encolado para procesamiento SRI.",
            usuario_id=usuario_id,
        )
        if commit:
            session.commit()
            session.refresh(tarea)
        else:
            session.flush()

        if background_tasks:
            background_tasks.add_task(self.procesar_documento_sri, tarea.id)
        return tarea

    def _default_scheduler(self, tarea_id: UUID, delay_seconds: int) -> None:
        timer = threading.Timer(delay_seconds, self.procesar_documento_sri, kwargs={"tarea_id": tarea_id})
        timer.daemon = True
        timer.start()

    def procesar_documento_sri(
        self,
        tarea_id: UUID,
        *,
        gateway: FEECOrquestadorGateway | None = None,
        scheduler: Callable[[UUID, int], None] | None = None,
    ) -> None:
        gateway_impl = gateway or self.gateway
        scheduler_impl = scheduler or self._default_scheduler

        with Session(self.db_engine) as session:
            tarea = session.get(DocumentoSriCola, tarea_id)
            if not tarea or not tarea.activo:
                return
            if tarea.estado in {EstadoColaSri.COMPLETADO, EstadoColaSri.FALLIDO}:
                return

            retencion = session.get(Retencion, tarea.entidad_id)
            if not retencion or not retencion.activo:
                tarea.estado = EstadoColaSri.FALLIDO
                tarea.ultimo_error = "Entidad asociada no encontrada."
                session.add(tarea)
                session.commit()
                return

            tarea.estado = EstadoColaSri.PROCESANDO
            tarea.intentos_realizados += 1
            retencion.sri_intentos = tarea.intentos_realizados
            session.add(tarea)
            session.add(retencion)
            session.commit()

            payload = json.loads(tarea.payload_json)
            try:
                respuesta = gateway_impl.enviar_documento(
                    tipo_documento=tarea.tipo_documento,
                    payload=payload,
                )
            except (TimeoutError, ConnectionError, OSError) as exc:
                error = str(exc) or "Timeout de red con SRI"
                estado_anterior = retencion.estado_sri.value
                if tarea.intentos_realizados < tarea.max_intentos:
                    delay = 2 ** (tarea.intentos_realizados - 1)
                    tarea.estado = EstadoColaSri.REINTENTO_PROGRAMADO
                    tarea.proximo_intento_en = datetime.utcnow() + timedelta(seconds=delay)
                    tarea.ultimo_error = error

                    retencion.estado_sri = EstadoSriDocumento.REINTENTO
                    retencion.sri_ultimo_error = error
                    session.add(tarea)
                    session.add(retencion)
                    self._historial(
                        session,
                        retencion=retencion,
                        estado_anterior=estado_anterior,
                        estado_nuevo=EstadoSriDocumento.REINTENTO.value,
                        motivo=f"Error de red SRI. Reintento programado en {delay}s. {error}",
                        usuario_id=retencion.usuario_auditoria,
                    )
                    session.commit()
                    scheduler_impl(tarea.id, delay)
                    return

                tarea.estado = EstadoColaSri.FALLIDO
                tarea.ultimo_error = error
                retencion.estado_sri = EstadoSriDocumento.ERROR
                retencion.sri_ultimo_error = error
                session.add(tarea)
                session.add(retencion)
                self._historial(
                    session,
                    retencion=retencion,
                    estado_anterior=estado_anterior,
                    estado_nuevo=EstadoSriDocumento.ERROR.value,
                    motivo=f"Maximo de reintentos agotado. {error}",
                    usuario_id=retencion.usuario_auditoria,
                )
                session.commit()
                return

            estado = str(respuesta.get("estado", "")).upper()
            mensaje = str(respuesta.get("mensaje") or "").strip()
            estado_anterior = retencion.estado_sri.value

            if estado == EstadoSriDocumento.AUTORIZADO.value:
                tarea.estado = EstadoColaSri.COMPLETADO
                tarea.ultimo_error = None
                retencion.estado_sri = EstadoSriDocumento.AUTORIZADO
                retencion.sri_ultimo_error = None
                if retencion.estado == EstadoRetencion.ENCOLADA:
                    retencion.estado = EstadoRetencion.EMITIDA
                session.add(tarea)
                session.add(retencion)
                self._historial(
                    session,
                    retencion=retencion,
                    estado_anterior=estado_anterior,
                    estado_nuevo=EstadoSriDocumento.AUTORIZADO.value,
                    motivo=mensaje or "Documento autorizado por SRI.",
                    usuario_id=retencion.usuario_auditoria,
                )
                session.commit()
                return

            if estado == EstadoSriDocumento.RECHAZADO.value:
                tarea.estado = EstadoColaSri.FALLIDO
                tarea.ultimo_error = mensaje or "Documento rechazado por SRI."
                retencion.estado_sri = EstadoSriDocumento.RECHAZADO
                retencion.sri_ultimo_error = tarea.ultimo_error
                session.add(tarea)
                session.add(retencion)
                self._historial(
                    session,
                    retencion=retencion,
                    estado_anterior=estado_anterior,
                    estado_nuevo=EstadoSriDocumento.RECHAZADO.value,
                    motivo=tarea.ultimo_error,
                    usuario_id=retencion.usuario_auditoria,
                )
                session.commit()
                return

            tarea.estado = EstadoColaSri.FALLIDO
            tarea.ultimo_error = mensaje or f"Respuesta SRI desconocida: {estado or 'VACIO'}"
            retencion.estado_sri = EstadoSriDocumento.ERROR
            retencion.sri_ultimo_error = tarea.ultimo_error
            session.add(tarea)
            session.add(retencion)
            self._historial(
                session,
                retencion=retencion,
                estado_anterior=estado_anterior,
                estado_nuevo=EstadoSriDocumento.ERROR.value,
                motivo=tarea.ultimo_error,
                usuario_id=retencion.usuario_auditoria,
            )
            session.commit()
