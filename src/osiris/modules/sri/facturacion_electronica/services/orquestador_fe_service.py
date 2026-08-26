from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import func, or_
from sqlmodel import Session, select

from osiris.core.db import engine as default_engine
from osiris.modules.sri.core_sri.models import (
    DocumentoElectronico,
    DocumentoSriCola,
    EstadoSriDocumento,
    EstadoDocumentoElectronico,
    Retencion,
    TipoDocumentoElectronico,
    Venta,
)
from osiris.modules.sri.facturacion_electronica.services.sri_async_service import FEECOrquestadorGateway, SriAsyncService
from osiris.modules.sri.facturacion_electronica.services.venta_sri_async_service import FEECVentaGateway, VentaSriAsyncService


def _sync_estado_documento(
    documento: DocumentoElectronico,
    estado: EstadoDocumentoElectronico,
    *,
    mensaje: str | None = None,
) -> None:
    documento.estado_sri = estado
    documento.estado = estado
    if mensaje is not None:
        documento.mensajes_sri = mensaje


class OrquestadorFEService:
    def __init__(
        self,
        *,
        db_engine=None,
        venta_sri_service: VentaSriAsyncService | None = None,
        retencion_sri_service: SriAsyncService | None = None,
    ) -> None:
        self.db_engine = db_engine or default_engine
        self.venta_sri_service = venta_sri_service or VentaSriAsyncService(db_engine=self.db_engine)
        self.retencion_sri_service = retencion_sri_service or SriAsyncService(db_engine=self.db_engine)

    @staticmethod
    def _backoff_minutes(intentos: int) -> int:
        # 1er retry: 2min, luego 4, 8, 16...
        return 2 ** max(intentos, 1)

    @staticmethod
    def _obtener_documento_activo(
        session: Session,
        *,
        tipo_documento: TipoDocumentoElectronico,
        referencia_id: UUID,
    ) -> DocumentoElectronico | None:
        return session.exec(
            select(DocumentoElectronico).where(
                DocumentoElectronico.tipo_documento == tipo_documento,
                DocumentoElectronico.referencia_id == referencia_id,
                DocumentoElectronico.activo.is_(True),
            )
        ).first()

    @staticmethod
    def _obtener_tarea(
        session: Session,
        *,
        referencia_id: UUID,
        tipo_documento_cola: str,
    ) -> DocumentoSriCola | None:
        return session.exec(
            select(DocumentoSriCola)
            .where(
                DocumentoSriCola.entidad_id == referencia_id,
                DocumentoSriCola.tipo_documento == tipo_documento_cola,
                DocumentoSriCola.activo.is_(True),
            )
            .order_by(DocumentoSriCola.creado_en.desc())
        ).first()

    def encolar_documento(
        self,
        session: Session,
        *,
        tipo_documento: TipoDocumentoElectronico | str,
        referencia_id: UUID,
        usuario_id: str | None,
        background_tasks: BackgroundTasks | None = None,
        commit: bool = True,
    ) -> DocumentoElectronico:
        tipo = (
            tipo_documento
            if isinstance(tipo_documento, TipoDocumentoElectronico)
            else TipoDocumentoElectronico(tipo_documento)
        )

        if tipo == TipoDocumentoElectronico.FACTURA:
            self.venta_sri_service.encolar_venta(
                session,
                venta_id=referencia_id,
                usuario_id=usuario_id,
                background_tasks=background_tasks,
                commit=False,
            )
            documento = self._obtener_documento_activo(
                session,
                tipo_documento=TipoDocumentoElectronico.FACTURA,
                referencia_id=referencia_id,
            )
            if documento is None:
                documento = session.exec(
                    select(DocumentoElectronico).where(
                        DocumentoElectronico.venta_id == referencia_id,
                        DocumentoElectronico.activo.is_(True),
                    )
                ).first()
                if documento is None:
                    raise HTTPException(status_code=500, detail="No se pudo crear el documento electrónico de factura.")
            documento.tipo_documento = TipoDocumentoElectronico.FACTURA
            documento.referencia_id = referencia_id
            documento.venta_id = referencia_id
            documento.usuario_auditoria = usuario_id
            documento.intentos = 0
            documento.next_retry_at = datetime.utcnow()
            _sync_estado_documento(documento, EstadoDocumentoElectronico.EN_COLA, mensaje=None)
            session.add(documento)
        elif tipo == TipoDocumentoElectronico.RETENCION:
            self.retencion_sri_service.encolar_retencion(
                session,
                retencion_id=referencia_id,
                usuario_id=usuario_id,
                background_tasks=background_tasks,
                commit=False,
            )
            documento = self._obtener_documento_activo(
                session,
                tipo_documento=TipoDocumentoElectronico.RETENCION,
                referencia_id=referencia_id,
            )
            if documento is None:
                documento = DocumentoElectronico(
                    tipo_documento=TipoDocumentoElectronico.RETENCION,
                    referencia_id=referencia_id,
                    clave_acceso=None,
                    venta_id=None,
                    usuario_auditoria=usuario_id,
                    activo=True,
                )
            documento.tipo_documento = TipoDocumentoElectronico.RETENCION
            documento.referencia_id = referencia_id
            documento.usuario_auditoria = usuario_id
            documento.intentos = 0
            documento.next_retry_at = datetime.utcnow()
            _sync_estado_documento(documento, EstadoDocumentoElectronico.EN_COLA, mensaje=None)
            session.add(documento)
        else:
            raise HTTPException(status_code=400, detail="Tipo de documento no soportado para orquestación FE-EC.")

        if commit:
            session.commit()
            session.refresh(documento)
        else:
            session.flush()
        return documento

    def procesar_documento(
        self,
        doc_id: UUID,
        *,
        venta_gateway: FEECVentaGateway | None = None,
        retencion_gateway: FEECOrquestadorGateway | None = None,
    ) -> None:
        with Session(self.db_engine) as session:
            documento = session.get(DocumentoElectronico, doc_id)
            if not documento or not documento.activo:
                return

            if documento.tipo_documento == TipoDocumentoElectronico.FACTURA:
                if documento.referencia_id is None:
                    raise HTTPException(status_code=400, detail="Documento de factura sin referencia_id.")
                tarea = self._obtener_tarea(
                    session,
                    referencia_id=documento.referencia_id,
                    tipo_documento_cola="VENTA",
                )
                if tarea is None:
                    raise HTTPException(status_code=404, detail="No existe tarea SRI para la factura.")
                _sync_estado_documento(documento, EstadoDocumentoElectronico.FIRMADO)
                session.add(documento)
                session.commit()

                self.venta_sri_service.procesar_documento_sri(
                    tarea.id,
                    gateway=venta_gateway,
                    scheduler=lambda _task_id, _delay: None,
                )

                session.refresh(documento)
                venta = session.get(Venta, documento.referencia_id)
                if venta is None:
                    return
                if venta.estado_sri == EstadoSriDocumento.AUTORIZADO:
                    _sync_estado_documento(documento, EstadoDocumentoElectronico.AUTORIZADO, mensaje=None)
                    documento.next_retry_at = None
                elif venta.estado_sri == EstadoSriDocumento.RECHAZADO:
                    _sync_estado_documento(
                        documento,
                        EstadoDocumentoElectronico.RECHAZADO,
                        mensaje=venta.sri_ultimo_error,
                    )
                    documento.next_retry_at = None
                else:
                    _sync_estado_documento(
                        documento,
                        EstadoDocumentoElectronico.RECIBIDO,
                        mensaje=venta.sri_ultimo_error,
                    )
                    documento.intentos += 1
                    if documento.intentos < 5:
                        documento.next_retry_at = datetime.utcnow() + timedelta(
                            minutes=self._backoff_minutes(documento.intentos)
                        )
                    else:
                        documento.next_retry_at = None
                session.add(documento)
                session.commit()
                return

            if documento.tipo_documento == TipoDocumentoElectronico.RETENCION:
                if documento.referencia_id is None:
                    raise HTTPException(status_code=400, detail="Documento de retención sin referencia_id.")
                tarea = self._obtener_tarea(
                    session,
                    referencia_id=documento.referencia_id,
                    tipo_documento_cola="RETENCION",
                )
                if tarea is None:
                    raise HTTPException(status_code=404, detail="No existe tarea SRI para la retención.")
                _sync_estado_documento(documento, EstadoDocumentoElectronico.FIRMADO)
                session.add(documento)
                session.commit()

                self.retencion_sri_service.procesar_documento_sri(
                    tarea.id,
                    gateway=retencion_gateway,
                    scheduler=lambda _task_id, _delay: None,
                )

                session.refresh(documento)
                retencion = session.get(Retencion, documento.referencia_id)
                if retencion is None:
                    return
                if retencion.estado_sri == EstadoSriDocumento.AUTORIZADO:
                    _sync_estado_documento(documento, EstadoDocumentoElectronico.AUTORIZADO, mensaje=None)
                    documento.next_retry_at = None
                elif retencion.estado_sri == EstadoSriDocumento.RECHAZADO:
                    _sync_estado_documento(
                        documento,
                        EstadoDocumentoElectronico.RECHAZADO,
                        mensaje=retencion.sri_ultimo_error,
                    )
                    documento.next_retry_at = None
                else:
                    _sync_estado_documento(
                        documento,
                        EstadoDocumentoElectronico.RECIBIDO,
                        mensaje=retencion.sri_ultimo_error,
                    )
                    documento.intentos += 1
                    if documento.intentos < 5:
                        documento.next_retry_at = datetime.utcnow() + timedelta(
                            minutes=self._backoff_minutes(documento.intentos)
                        )
                    else:
                        documento.next_retry_at = None
                session.add(documento)
                session.commit()
                return

            raise HTTPException(status_code=400, detail="Tipo de documento no soportado para procesamiento FE-EC.")

    def procesar_cola(self, session: Session, *, now: datetime | None = None) -> int:
        now_dt = now or datetime.utcnow()
        documentos = list(
            session.exec(
                self._stmt_documentos_pendientes(
                    now=now_dt,
                    incluir_no_vencidos=False,
                    tipo_documento=None,
                ).order_by(DocumentoElectronico.creado_en.asc())
            ).all()
        )
        ids = [doc.id for doc in documentos]
        for doc_id in ids:
            self.procesar_documento(doc_id)
        return len(ids)

    @staticmethod
    def _stmt_documentos_pendientes(
        *,
        now: datetime | None = None,
        incluir_no_vencidos: bool = True,
        tipo_documento: TipoDocumentoElectronico | None = None,
    ):
        now_dt = now or datetime.utcnow()
        stmt = select(DocumentoElectronico).where(
            DocumentoElectronico.activo.is_(True),
            DocumentoElectronico.estado_sri.in_(
                [EstadoDocumentoElectronico.EN_COLA, EstadoDocumentoElectronico.RECIBIDO]
            ),
            DocumentoElectronico.intentos < 5,
        )
        if not incluir_no_vencidos:
            stmt = stmt.where(
                or_(DocumentoElectronico.next_retry_at.is_(None), DocumentoElectronico.next_retry_at <= now_dt)
            )
        if tipo_documento is not None:
            stmt = stmt.where(DocumentoElectronico.tipo_documento == tipo_documento)
        return stmt

    def listar_documentos_pendientes(
        self,
        session: Session,
        *,
        limit: int,
        offset: int,
        incluir_no_vencidos: bool = True,
        tipo_documento: TipoDocumentoElectronico = TipoDocumentoElectronico.FACTURA,
    ):
        stmt = self._stmt_documentos_pendientes(
            incluir_no_vencidos=incluir_no_vencidos,
            tipo_documento=tipo_documento,
        )
        total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
        items = list(
            session.exec(
                stmt.order_by(DocumentoElectronico.creado_en.asc())
                .offset(offset)
                .limit(limit)
            ).all()
        )
        return items, int(total)

    def procesar_documentos_ids(self, documento_ids: list[UUID]) -> tuple[int, list[UUID], list[str]]:
        procesados = 0
        ids_procesados: list[UUID] = []
        errores: list[str] = []

        for doc_id in documento_ids:
            try:
                self.procesar_documento(doc_id)
                procesados += 1
                ids_procesados.append(doc_id)
            except HTTPException as exc:
                errores.append(f"{doc_id}: {exc.detail}")
            except Exception as exc:  # pragma: no cover - respaldo operativo
                errores.append(f"{doc_id}: {exc}")

        return procesados, ids_procesados, errores

    def procesar_documentos_pendientes(
        self,
        session: Session,
        *,
        tipo_documento: TipoDocumentoElectronico = TipoDocumentoElectronico.FACTURA,
        incluir_no_vencidos: bool = True,
    ) -> tuple[int, list[UUID], list[str]]:
        documentos = list(
            session.exec(
                self._stmt_documentos_pendientes(
                    incluir_no_vencidos=incluir_no_vencidos,
                    tipo_documento=tipo_documento,
                ).order_by(DocumentoElectronico.creado_en.asc())
            ).all()
        )
        return self.procesar_documentos_ids([doc.id for doc in documentos])
