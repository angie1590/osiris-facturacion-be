from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, Response
from sqlmodel import Session

from osiris.core.audit_context import get_current_user_id
from osiris.core.db import get_session
from osiris.domain.schemas import PaginatedResponse
from osiris.modules.sri.facturacion_electronica.schemas import (
    FEDocumentoColaRead,
    FEProcesarColaRead,
    FEProcesarDocumentosRead,
    FEProcesarDocumentosRequest,
)
from osiris.modules.sri.core_sri.models import TipoDocumentoElectronico
from osiris.modules.sri.facturacion_electronica.services.documento_service import DocumentoElectronicoService
from osiris.modules.sri.facturacion_electronica.services.orquestador_fe_service import OrquestadorFEService
from osiris.modules.sri.facturacion_electronica.services.sri_async_service import SriAsyncService
from osiris.modules.sri.facturacion_electronica.services.venta_sri_async_service import VentaSriAsyncService
from osiris.utils.pagination import build_pagination_meta


COMMON_RESPONSES = {
    400: {"description": "Solicitud inválida para estado del documento."},
    403: {"description": "Usuario sin autorización para el documento solicitado."},
    404: {"description": "Documento o recurso relacionado no encontrado."},
}

router = APIRouter()
fe_router = APIRouter(prefix="/api/v1/fe", tags=["Facturación Electrónica"])
documentos_router = APIRouter(prefix="/api/v1/documentos", tags=["Documentos Electrónicos"])
documento_service = DocumentoElectronicoService()
orquestador_fe_service = OrquestadorFEService(
    venta_sri_service=VentaSriAsyncService(),
    retencion_sri_service=SriAsyncService(),
)


@fe_router.post("/procesar-cola", response_model=FEProcesarColaRead, summary="Procesar cola SRI", responses=COMMON_RESPONSES)
def procesar_cola_fe(session: Session = Depends(get_session)):
    """Procesa documentos electrónicos pendientes en cola aplicando reglas de reintentos y contingencia."""
    procesados = orquestador_fe_service.procesar_cola(session)
    return {"procesados": procesados}


@fe_router.get("/cola", response_model=PaginatedResponse[FEDocumentoColaRead], summary="Listar cola FE", responses=COMMON_RESPONSES)
def listar_cola_fe(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    incluir_no_vencidos: bool = Query(True),
    tipo_documento: TipoDocumentoElectronico = Query(default=TipoDocumentoElectronico.FACTURA),
    session: Session = Depends(get_session),
):
    """Lista documentos en cola FE pendientes por procesar para operación manual o monitoreo."""
    items, total = orquestador_fe_service.listar_documentos_pendientes(
        session,
        limit=limit,
        offset=offset,
        incluir_no_vencidos=incluir_no_vencidos,
        tipo_documento=tipo_documento,
    )
    return {"items": items, "meta": build_pagination_meta(total=total, limit=limit, offset=offset)}


@fe_router.post(
    "/procesar/{documento_id}",
    response_model=FEProcesarDocumentosRead,
    summary="Procesar un documento FE manualmente",
    responses=COMMON_RESPONSES,
)
def procesar_documento_manual(documento_id: UUID):
    """Fuerza el procesamiento inmediato de un documento puntual de facturación electrónica."""
    procesados, ids_procesados, errores = orquestador_fe_service.procesar_documentos_ids([documento_id])
    return {"procesados": procesados, "ids_procesados": ids_procesados, "errores": errores}


@fe_router.post(
    "/procesar-manual",
    response_model=FEProcesarDocumentosRead,
    summary="Procesar varios/todos los documentos FE manualmente",
    responses=COMMON_RESPONSES,
)
def procesar_documentos_manual(payload: FEProcesarDocumentosRequest, session: Session = Depends(get_session)):
    """Procesa manualmente varios documentos o toda la cola FE según criterios enviados."""
    if payload.documento_ids:
        procesados, ids_procesados, errores = orquestador_fe_service.procesar_documentos_ids(payload.documento_ids)
        return {"procesados": procesados, "ids_procesados": ids_procesados, "errores": errores}

    if not payload.procesar_todos:
        return {"procesados": 0, "ids_procesados": [], "errores": ["Debe enviar documento_ids o procesar_todos=true."]}

    procesados, ids_procesados, errores = orquestador_fe_service.procesar_documentos_pendientes(
        session,
        tipo_documento=payload.tipo_documento,
        incluir_no_vencidos=payload.incluir_no_vencidos,
    )
    return {"procesados": procesados, "ids_procesados": ids_procesados, "errores": errores}


@documentos_router.get("/{documento_id}/xml", summary="Descargar XML autorizado", responses=COMMON_RESPONSES, response_class=Response)
def descargar_xml_documento(documento_id: UUID, session: Session = Depends(get_session)):
    """Devuelve el XML autorizado de un documento electrónico si ya fue aceptado por el SRI."""
    xml = documento_service.obtener_xml_autorizado(session, documento_id=documento_id, user_id=get_current_user_id())
    return Response(content=xml, media_type="application/xml")


@documentos_router.get("/{documento_id}/ride", summary="Descargar RIDE", responses=COMMON_RESPONSES, response_class=HTMLResponse)
def descargar_ride_documento(documento_id: UUID, session: Session = Depends(get_session)):
    """Genera una representación HTML del RIDE para visualización y descarga controlada."""
    html = documento_service.obtener_ride_html(session, documento_id=documento_id, user_id=get_current_user_id())
    return HTMLResponse(content=html)


router.include_router(fe_router)
router.include_router(documentos_router)
