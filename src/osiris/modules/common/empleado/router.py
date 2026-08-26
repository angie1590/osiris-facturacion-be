from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.domain.schemas import PaginatedResponse
from osiris.modules.common.empleado.models import EmpleadoCreate, EmpleadoRead, EmpleadoUpdate
from osiris.modules.common.empleado.service import EmpleadoService


router = APIRouter(prefix="/api/v1/empleados", tags=["Empleados"])
service = EmpleadoService()


@router.get("", response_model=PaginatedResponse[EmpleadoRead])
def list_empleados(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    only_active: bool = Query(True),
    session: Session = Depends(get_session),
):
    items, meta = service.list_paginated(session, only_active=only_active, limit=limit, offset=offset)
    return {"items": items, "meta": meta}


@router.get("/{item_id}", response_model=EmpleadoRead)
def get_empleado(item_id: UUID = Path(...), session: Session = Depends(get_session)):
    obj = service.get(session, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"Empleado {item_id} not found")
    return obj


@router.post("", response_model=EmpleadoRead, status_code=status.HTTP_201_CREATED)
def create_empleado(payload: EmpleadoCreate = Body(...), session: Session = Depends(get_session)):
    return service.create(session, payload.model_dump(exclude_unset=True))


@router.put("/{item_id}", response_model=EmpleadoRead)
def update_empleado(
    item_id: UUID = Path(...),
    payload: EmpleadoUpdate = Body(...),
    session: Session = Depends(get_session),
):
    updated = service.update(session, item_id, payload.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Empleado {item_id} not found")
    return updated


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_empleado(item_id: UUID = Path(...), session: Session = Depends(get_session)):
    ok = service.delete(session, item_id)
    if ok is None:
        raise HTTPException(status_code=404, detail=f"Empleado {item_id} not found")
