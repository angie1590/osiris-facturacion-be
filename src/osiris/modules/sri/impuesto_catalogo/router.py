from __future__ import annotations

from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.domain.schemas import PaginatedResponse
from osiris.modules.sri.impuesto_catalogo.entity import TipoImpuesto
from osiris.modules.sri.impuesto_catalogo.models import (
    ImpuestoCatalogoCreate,
    ImpuestoCatalogoRead,
    ImpuestoCatalogoUpdate,
)
from osiris.modules.sri.impuesto_catalogo.service import ImpuestoCatalogoService
from osiris.utils.pagination import build_pagination_meta


router = APIRouter(prefix="/api/v1/impuestos", tags=["Impuestos"])
service = ImpuestoCatalogoService()


@router.get("", response_model=PaginatedResponse[ImpuestoCatalogoRead])
def listar_catalogo_impuestos(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    tipo_impuesto: Optional[TipoImpuesto] = None,
    solo_vigentes: bool = False,
    session: Session = Depends(get_session),
):
    if tipo_impuesto:
        if solo_vigentes:
            items = service.list_by_tipo(session, tipo_impuesto, solo_vigentes=True)
        else:
            items = service.list_by_tipo(session, tipo_impuesto, solo_vigentes=False)
        total = len(items)
        items = items[offset : offset + limit]
    else:
        items, meta = service.list_paginated(session, limit=limit, offset=offset)

    computed_meta = build_pagination_meta(total, limit, offset) if tipo_impuesto else meta

    return PaginatedResponse(items=[ImpuestoCatalogoRead.model_validate(item) for item in items], meta=computed_meta)


@router.get("/activos-vigentes", response_model=List[ImpuestoCatalogoRead])
def listar_impuestos_activos_vigentes(
    fecha: Optional[date] = Query(None, description="Fecha de vigencia (por defecto hoy)"),
    session: Session = Depends(get_session),
):
    items = service.list_activos_vigentes(session, fecha)
    return [ImpuestoCatalogoRead.model_validate(item) for item in items]


@router.get("/{impuesto_id}", response_model=ImpuestoCatalogoRead)
def obtener_impuesto(impuesto_id: UUID, session: Session = Depends(get_session)):
    impuesto = service.get(session, impuesto_id)
    return ImpuestoCatalogoRead.model_validate(impuesto)


@router.post("", response_model=ImpuestoCatalogoRead, status_code=201)
def crear_impuesto(payload: ImpuestoCatalogoCreate, session: Session = Depends(get_session)):
    impuesto = service.create(session, payload.model_dump(exclude_unset=True))
    return ImpuestoCatalogoRead.model_validate(impuesto)


@router.put("/{impuesto_id}", response_model=ImpuestoCatalogoRead)
def actualizar_impuesto(impuesto_id: UUID, payload: ImpuestoCatalogoUpdate, session: Session = Depends(get_session)):
    impuesto = service.update(session, impuesto_id, payload.model_dump(exclude_unset=True))
    return ImpuestoCatalogoRead.model_validate(impuesto)


@router.delete("/{impuesto_id}", status_code=204)
def desactivar_impuesto(impuesto_id: UUID, session: Session = Depends(get_session)):
    service.delete(session, impuesto_id)
    return None
