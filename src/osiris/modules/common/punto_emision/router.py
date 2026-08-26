from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.domain.schemas import PaginatedResponse
from osiris.modules.common.punto_emision.entity import TipoDocumentoSRI
from osiris.modules.common.punto_emision.models import (
    AjusteManualSecuencialRequest,
    PuntoEmisionCreate,
    PuntoEmisionRead,
    PuntoEmisionSecuencialRead,
    PuntoEmisionUpdate,
    SiguienteSecuencialRequest,
    SiguienteSecuencialResponse,
)
from osiris.modules.common.punto_emision.service import PuntoEmisionService


router = APIRouter(prefix="/api/v1/puntos-emision", tags=["Puntos de Emisión"])
service = PuntoEmisionService()


@router.get("", response_model=PaginatedResponse[PuntoEmisionRead])
def list_puntos_emision(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    only_active: bool = Query(True),
    session: Session = Depends(get_session),
):
    items, meta = service.list_paginated(session, only_active=only_active, limit=limit, offset=offset)
    return {"items": items, "meta": meta}


@router.get("/{item_id}", response_model=PuntoEmisionRead)
def get_punto_emision(item_id: UUID = Path(...), session: Session = Depends(get_session)):
    obj = service.get(session, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"Punto-emision {item_id} not found")
    return obj


@router.post("", response_model=PuntoEmisionRead, status_code=status.HTTP_201_CREATED)
def create_punto_emision(payload: PuntoEmisionCreate = Body(...), session: Session = Depends(get_session)):
    return service.create(session, payload.model_dump(exclude_unset=True))


@router.put("/{item_id}", response_model=PuntoEmisionRead)
def update_punto_emision(
    item_id: UUID = Path(...),
    payload: PuntoEmisionUpdate = Body(...),
    session: Session = Depends(get_session),
):
    updated = service.update(session, item_id, payload.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Punto-emision {item_id} not found")
    return updated


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_punto_emision(item_id: UUID = Path(...), session: Session = Depends(get_session)):
    ok = service.delete(session, item_id)
    if ok is None:
        raise HTTPException(status_code=404, detail=f"Punto-emision {item_id} not found")


@router.post("/{punto_emision_id}/secuenciales/{tipo_documento}/siguiente", response_model=SiguienteSecuencialResponse)
def obtener_siguiente_secuencial(
    punto_emision_id: UUID = Path(..., description="ID del punto de emisión"),
    tipo_documento: TipoDocumentoSRI = Path(..., description="Tipo de documento SRI"),
    payload: SiguienteSecuencialRequest = Body(default=SiguienteSecuencialRequest()),
    session: Session = Depends(get_session),
):
    secuencial = service.obtener_siguiente_secuencial_formateado(
        session,
        punto_emision_id=punto_emision_id,
        tipo_documento=tipo_documento,
        usuario_auditoria=payload.usuario_auditoria,
    )
    return SiguienteSecuencialResponse(secuencial=secuencial)


@router.post("/{punto_emision_id}/secuenciales/{tipo_documento}/ajuste-manual", response_model=PuntoEmisionSecuencialRead)
def ajustar_secuencial_manual(
    punto_emision_id: UUID = Path(..., description="ID del punto de emisión"),
    tipo_documento: TipoDocumentoSRI = Path(..., description="Tipo de documento SRI"),
    payload: AjusteManualSecuencialRequest = Body(...),
    session: Session = Depends(get_session),
):
    return service.ajustar_secuencial_manual(
        session,
        punto_emision_id=punto_emision_id,
        tipo_documento=tipo_documento,
        nuevo_secuencial=payload.nuevo_secuencial,
        usuario_id=payload.usuario_id,
        justificacion=payload.justificacion,
    )
