from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.core.auth import get_current_usuario
from osiris.core.directory_permissions import directory_permission
from osiris.domain.schemas import PaginatedResponse
from osiris.modules.common.rol.entity import Rol
from osiris.modules.common.rol.models import RolCreate, RolRead, RolUpdate
from osiris.modules.common.rol.service import RolService

router = APIRouter(prefix="/api/v1/roles", tags=["Roles"])
service = RolService()


@router.get(
    "",
    response_model=PaginatedResponse[RolRead],
    dependencies=[Depends(get_current_usuario)],
)
def list_roles(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    only_active: bool = Query(True),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    items, meta = service.list_paginated(
        session, only_active=only_active, limit=limit, offset=offset
    )
    return {"items": items, "meta": meta}


@router.get(
    "/{item_id}", response_model=RolRead, dependencies=[Depends(get_current_usuario)]
)
def get_rol(item_id: UUID = Path(...), session: Session = Depends(get_session)) -> Rol:
    obj = service.get(session, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"Role {item_id} not found")
    return obj


@router.post(
    "",
    response_model=RolRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(directory_permission("USUARIOS", "actualizar"))],
)
def create_rol(
    payload: RolCreate = Body(...), session: Session = Depends(get_session)
) -> Rol:
    return service.create(session, payload.model_dump(exclude_unset=True))


@router.put(
    "/{item_id}",
    response_model=RolRead,
    dependencies=[Depends(directory_permission("USUARIOS", "actualizar"))],
)
def update_rol(
    item_id: UUID = Path(...),
    payload: RolUpdate = Body(...),
    session: Session = Depends(get_session),
) -> Rol:
    updated = service.update(session, item_id, payload.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Role {item_id} not found")
    return updated


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(directory_permission("USUARIOS", "actualizar"))],
)
def delete_rol(
    item_id: UUID = Path(...), session: Session = Depends(get_session)
) -> None:
    ok = service.delete(session, item_id)
    if ok is None:
        raise HTTPException(status_code=404, detail=f"Role {item_id} not found")
