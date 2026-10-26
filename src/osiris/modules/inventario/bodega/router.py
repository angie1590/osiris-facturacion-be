from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.modules.inventario.bodega.entity import Bodega
from osiris.modules.inventario.bodega.models import (
    BodegaCreate,
    BodegaRead,
    BodegaUpdate,
)
from osiris.modules.inventario.bodega.service import BodegaService

router = APIRouter(prefix="/api/v1/bodegas", tags=["Bodegas"])
service = BodegaService()


@router.get("", response_model=list[BodegaRead])
def list_bodegas(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    empresa_id: Optional[UUID] = Query(None),
    sucursal_id: Optional[UUID] = Query(None),
    session: Session = Depends(get_session),
) -> list[Bodega]:
    return service.list_paginated(
        session,
        skip=skip,
        limit=limit,
        empresa_id=empresa_id,
        sucursal_id=sucursal_id,
    )


@router.get("/{id}", response_model=BodegaRead)
def get_bodega(id: UUID, session: Session = Depends(get_session)) -> Bodega:
    entity = service.get(session, id)
    if not entity:
        raise HTTPException(status_code=404, detail="Bodega no encontrada")
    return entity


@router.post("", response_model=BodegaRead, status_code=201)
def create_bodega(dto: BodegaCreate, session: Session = Depends(get_session)) -> Bodega:
    return service.create(session, dto, usuario_auditoria="api")


@router.put("/{id}", response_model=BodegaRead)
def update_bodega(
    id: UUID, dto: BodegaUpdate, session: Session = Depends(get_session)
) -> Bodega:
    entity = service.update(session, id, dto, usuario_auditoria="api")
    if not entity:
        raise HTTPException(status_code=404, detail="Bodega no encontrada")
    return entity


@router.delete("/{id}", status_code=204)
def delete_bodega(id: UUID, session: Session = Depends(get_session)) -> None:
    success = service.delete(session, id, usuario_auditoria="api")
    if not success:
        raise HTTPException(status_code=404, detail="Bodega no encontrada")
