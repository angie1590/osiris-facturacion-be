from __future__ import annotations

from uuid import UUID
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.core.directory_permissions import directory_permission
from osiris.domain.schemas import PaginatedResponse
from osiris.modules.common.empleado.models import (
    EmpleadoCreate,
    EmpleadoRead,
    EmpleadoUpdate,
)
from osiris.modules.common.empleado.service import EmpleadoService

router = APIRouter(prefix="/api/v1/empleados", tags=["Empleados"])
service = EmpleadoService()


@router.get(
    "",
    response_model=PaginatedResponse[EmpleadoRead],
    dependencies=[Depends(directory_permission("EMPLEADOS", "leer"))],
)
def list_empleados(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    only_active: bool = Query(True),
    q: str | None = Query(None),
    identificacion: str | None = Query(None),
    estado: str | None = Query(None),
    sort_by: str = Query("creado_en"),
    sort_order: str = Query("desc"),
    empresa_id: UUID | None = Query(None),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    items, meta = service.list_paginated(
        session,
        only_active=only_active,
        limit=limit,
        offset=offset,
        q=q,
        identificacion=identificacion,
        estado=estado,
        sort_by=sort_by,
        sort_order=sort_order,
        empresa_id=empresa_id,
    )
    return {"items": items, "meta": meta}


@router.get(
    "/{item_id}",
    response_model=EmpleadoRead,
    dependencies=[Depends(directory_permission("EMPLEADOS", "leer"))],
)
def get_empleado(
    item_id: UUID = Path(...), session: Session = Depends(get_session)
) -> EmpleadoRead:
    obj = service.get(session, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"Empleado {item_id} not found")
    return service.to_read(session, obj)


@router.post(
    "",
    response_model=EmpleadoRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(directory_permission("EMPLEADOS", "crear"))],
)
def create_empleado(
    payload: EmpleadoCreate = Body(...), session: Session = Depends(get_session)
) -> EmpleadoRead:
    return service.to_read(
        session, service.create(session, payload.model_dump(exclude_unset=True))
    )


@router.put(
    "/{item_id}",
    response_model=EmpleadoRead,
    dependencies=[Depends(directory_permission("EMPLEADOS", "actualizar"))],
)
def update_empleado(
    item_id: UUID = Path(...),
    payload: EmpleadoUpdate = Body(...),
    session: Session = Depends(get_session),
) -> EmpleadoRead:
    updated = service.update(session, item_id, payload.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Empleado {item_id} not found")
    return service.to_read(session, updated)


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(directory_permission("EMPLEADOS", "eliminar"))],
)
def delete_empleado(
    item_id: UUID = Path(...), session: Session = Depends(get_session)
) -> None:
    ok = service.delete(session, item_id)
    if ok is None:
        raise HTTPException(status_code=404, detail=f"Empleado {item_id} not found")


@router.post(
    "/{item_id}/reactivar",
    response_model=EmpleadoRead,
    dependencies=[Depends(directory_permission("EMPLEADOS", "actualizar"))],
)
def reactivate_empleado(
    item_id: UUID, session: Session = Depends(get_session)
) -> EmpleadoRead:
    return service.to_read(session, service.reactivate(session, item_id))
