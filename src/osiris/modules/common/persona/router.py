from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.domain.schemas import PaginatedResponse
from osiris.modules.common.persona.models import PersonaCreate, PersonaRead, PersonaUpdate
from osiris.modules.common.persona.repository import PersonaRepository
from osiris.modules.common.persona.service import PersonaService


router = APIRouter(prefix="/api/v1/personas", tags=["Personas"])
service = PersonaService(repo=PersonaRepository())


@router.get("", response_model=PaginatedResponse[PersonaRead])
def list_personas(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    only_active: bool = Query(True),
    session: Session = Depends(get_session),
):
    items, meta = service.list_paginated(session, only_active=only_active, limit=limit, offset=offset)
    return {"items": items, "meta": meta}


@router.get("/{item_id}", response_model=PersonaRead)
def get_persona(item_id: UUID = Path(...), session: Session = Depends(get_session)):
    obj = service.get(session, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"Persona {item_id} not found")
    return obj


@router.post("", response_model=PersonaRead, status_code=status.HTTP_201_CREATED)
def create_persona(payload: PersonaCreate = Body(...), session: Session = Depends(get_session)):
    return service.create(session, payload.model_dump(exclude_unset=True))


@router.put("/{item_id}", response_model=PersonaRead)
def update_persona(
    item_id: UUID = Path(...),
    payload: PersonaUpdate = Body(...),
    session: Session = Depends(get_session),
):
    updated = service.update(session, item_id, payload.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Persona {item_id} not found")
    return updated


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_persona(item_id: UUID = Path(...), session: Session = Depends(get_session)):
    ok = service.delete(session, item_id)
    if ok is None:
        raise HTTPException(status_code=404, detail=f"Persona {item_id} not found")
