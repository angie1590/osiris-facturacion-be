from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, Response
from sqlmodel import Session

from osiris.core.audit_context import get_current_user_id
from osiris.core.db import get_session
from osiris.modules.impresion.schemas import ReimpresionRequest
from osiris.modules.impresion.services.impresion_service import ImpresionService


COMMON_RESPONSES = {
    400: {"description": "Solicitud inválida para el formato de impresión."},
    403: {"description": "Usuario sin permisos para la operación de impresión."},
    404: {"description": "Documento no encontrado o no disponible para impresión."},
}

router = APIRouter(prefix="/api/v1/impresion", tags=["Impresión"])
impresion_service = ImpresionService()


@router.get("/documento/{documento_id}/a4", summary="Generar RIDE A4", responses=COMMON_RESPONSES, response_class=Response)
def generar_ride_a4(documento_id: UUID, session: Session = Depends(get_session)):
    pdf_bytes = impresion_service.generar_ride_a4(session, documento_id=documento_id)
    headers = {"Content-Disposition": f'inline; filename="ride-{documento_id}.pdf"'}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@router.get("/documento/{documento_id}/ticket", summary="Generar ticket térmico", responses=COMMON_RESPONSES, response_class=HTMLResponse)
def generar_ticket_termico(
    documento_id: UUID,
    ancho: Literal["58mm", "80mm"] = Query(default="80mm"),
    session: Session = Depends(get_session),
):
    html = impresion_service.generar_ticket_termico_html(session, documento_id=documento_id, ancho=ancho)
    return HTMLResponse(content=html)


@router.get("/documento/{documento_id}/preimpresa", summary="Generar plantilla preimpresa", responses=COMMON_RESPONSES)
def generar_preimpresa_nota_venta(
    documento_id: UUID,
    formato: Literal["HTML", "PDF"] = Query(default="HTML"),
    session: Session = Depends(get_session),
):
    formato_normalizado = formato.upper()
    if formato_normalizado == "PDF":
        resultado = impresion_service.generar_preimpresa_pdf(session, documento_id=documento_id)
        headers = {"Content-Disposition": f'inline; filename="nota-preimpresa-{documento_id}.pdf"'}
        if resultado["warning"]:
            headers["X-Impresion-Warning"] = str(resultado["warning"])
        return Response(content=resultado["pdf"], media_type="application/pdf", headers=headers)

    resultado = impresion_service.generar_preimpresa_html(session, documento_id=documento_id)
    headers: dict[str, str] = {}
    if resultado["warning"]:
        headers["X-Impresion-Warning"] = str(resultado["warning"])
    return HTMLResponse(content=str(resultado["html"]), headers=headers)


@router.post("/documento/{documento_id}/reimprimir", summary="Solicitar reimpresión", responses=COMMON_RESPONSES)
def reimprimir_documento(
    documento_id: UUID,
    payload: ReimpresionRequest,
    session: Session = Depends(get_session),
):
    resultado = impresion_service.reimprimir_documento(
        session,
        documento_id=documento_id,
        motivo=payload.motivo,
        formato=payload.formato,
        user_id=get_current_user_id(),
    )
    headers = {"Content-Disposition": f'inline; filename="{resultado["filename"]}"'}
    if resultado["media_type"] == "application/pdf":
        return Response(content=resultado["content"], media_type="application/pdf", headers=headers)
    return HTMLResponse(content=resultado["content"], headers=headers)
