from __future__ import annotations

from uuid import UUID
from typing import Any, Literal, cast

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    status,
)
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.core.directory_permissions import directory_permission
from osiris.domain.schemas import PaginatedResponse
from osiris.modules.common.persona.models import (
    PersonaCreate,
    PersonaRead,
    PersonaUpdate,
)
from osiris.modules.common.persona.repository import PersonaRepository
from osiris.modules.common.persona.service import PersonaService
from osiris.modules.common.persona.entity import Persona

router = APIRouter(prefix="/api/v1/personas", tags=["Personas"])
service = PersonaService(repo=PersonaRepository())


@router.get(
    "/contrato", dependencies=[Depends(directory_permission("PERSONAS", "leer"))]
)
def directory_contract(request: Request) -> dict[str, Any]:
    return cast(dict[str, Any], request.app.openapi())


@router.get(
    "",
    response_model=PaginatedResponse[PersonaRead],
    dependencies=[Depends(directory_permission("PERSONAS", "leer"))],
)
def list_personas(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    only_active: bool = Query(True),
    identificacion: str | None = Query(None),
    q: str | None = Query(None),
    estado: Literal["activo", "inactivo"] | None = Query(None),
    sort_by: str | None = Query(None),
    sort_direction: Literal["asc", "desc"] = Query("asc"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    items, meta = service.list_paginated(
        session,
        only_active=only_active,
        limit=limit,
        offset=offset,
        identificacion=identificacion,
        q=q,
        estado=estado,
        sort_by=sort_by,
        sort_direction=sort_direction,
    )
    return {"items": items, "meta": meta}


@router.get(
    "/{item_id}/vinculos",
    dependencies=[Depends(directory_permission("PERSONAS", "leer"))],
)
def persona_links(
    item_id: UUID, session: Session = Depends(get_session)
) -> dict[str, Any]:
    return service.links(session, item_id)


@router.post(
    "/{item_id}/reactivar",
    response_model=PersonaRead,
    dependencies=[Depends(directory_permission("PERSONAS", "actualizar"))],
)
def reactivate_persona(
    item_id: UUID, session: Session = Depends(get_session)
) -> Persona:
    return service.reactivate(session, item_id)


@router.get(
    "/{item_id}",
    response_model=PersonaRead,
    dependencies=[Depends(directory_permission("PERSONAS", "leer"))],
)
def get_persona(
    item_id: UUID = Path(...), session: Session = Depends(get_session)
) -> Persona:
    obj = service.get(session, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"Persona {item_id} not found")
    return obj


@router.post(
    "",
    response_model=PersonaRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(directory_permission("PERSONAS", "crear"))],
)
def create_persona(
    payload: PersonaCreate = Body(...), session: Session = Depends(get_session)
) -> Persona:
    return service.create(session, payload.model_dump(exclude_unset=True))


@router.put(
    "/{item_id}",
    response_model=PersonaRead,
    dependencies=[Depends(directory_permission("PERSONAS", "actualizar"))],
)
def update_persona(
    item_id: UUID = Path(...),
    payload: PersonaUpdate = Body(...),
    session: Session = Depends(get_session),
) -> Persona:
    updated = service.update(session, item_id, payload.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Persona {item_id} not found")
    return updated


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(directory_permission("PERSONAS", "eliminar"))],
)
def delete_persona(
    item_id: UUID = Path(...), session: Session = Depends(get_session)
) -> None:
    ok = service.delete(session, item_id)
    if ok is None:
        raise HTTPException(status_code=404, detail=f"Persona {item_id} not found")
