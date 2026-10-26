from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.core.directory_permissions import directory_permission
from osiris.domain.schemas import PaginatedResponse
from osiris.modules.common.rol_modulo_permiso.entity import RolModuloPermiso
from osiris.modules.common.rol_modulo_permiso.models import (
    RolModuloPermisoCreate,
    RolModuloPermisoRead,
    RolModuloPermisoUpdate,
)
from osiris.modules.common.rol_modulo_permiso.service import RolModuloPermisoService

router = APIRouter(prefix="/api/v1/roles-modulos-permisos", tags=["Permisos de Módulo"])
service = RolModuloPermisoService()


@router.get(
    "",
    response_model=PaginatedResponse[RolModuloPermisoRead],
    dependencies=[Depends(directory_permission("USUARIOS", "leer"))],
)
def list_permisos(
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
    "/{item_id}",
    response_model=RolModuloPermisoRead,
    dependencies=[Depends(directory_permission("USUARIOS", "leer"))],
)
def get_permiso(
    item_id: UUID = Path(...), session: Session = Depends(get_session)
) -> RolModuloPermiso:
    obj = service.get(session, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"Permiso {item_id} not found")
    return obj


@router.post(
    "",
    response_model=RolModuloPermisoRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(directory_permission("USUARIOS", "actualizar"))],
)
def create_permiso(
    payload: RolModuloPermisoCreate = Body(...), session: Session = Depends(get_session)
) -> RolModuloPermiso:
    return service.create(session, payload.model_dump(exclude_unset=True))


@router.put(
    "/{item_id}",
    response_model=RolModuloPermisoRead,
    dependencies=[Depends(directory_permission("USUARIOS", "actualizar"))],
)
def update_permiso(
    item_id: UUID = Path(...),
    payload: RolModuloPermisoUpdate = Body(...),
    session: Session = Depends(get_session),
) -> RolModuloPermiso:
    updated = service.update(session, item_id, payload.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Permiso {item_id} not found")
    return updated


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(directory_permission("USUARIOS", "actualizar"))],
)
def delete_permiso(
    item_id: UUID = Path(...), session: Session = Depends(get_session)
) -> None:
    ok = service.delete(session, item_id)
    if ok is None:
        raise HTTPException(status_code=404, detail=f"Permiso {item_id} not found")
