from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from sqlmodel import Session

from osiris.core.catalog_permissions import catalog_permission
from osiris.core.db import get_session
from osiris.domain.schemas import PaginatedResponse
from osiris.modules.common.unidad.models import UnidadCreate, UnidadRead, UnidadUpdate
from osiris.modules.common.unidad.service import UnidadService

router = APIRouter(prefix="/api/v1/unidades", tags=["Unidades"])
service = UnidadService()
read_units_permission = catalog_permission("read_units")
create_unit_permission = catalog_permission("create_unit")
update_unit_permission = catalog_permission("update_unit")
deactivate_unit_permission = catalog_permission("deactivate_unit")
reactivate_unit_permission = catalog_permission("reactivate_unit")


@router.get(
    "",
    response_model=PaginatedResponse[UnidadRead],
    dependencies=[Depends(read_units_permission)],
)
def list_unidades(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    only_active: bool = Query(True),
    q: str | None = Query(None),
    magnitud_codigo: str | None = Query(None, min_length=1, max_length=64),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    items, meta = service.list_paginated(
        session,
        only_active=only_active,
        limit=limit,
        offset=offset,
        q=q,
        magnitud_codigo=magnitud_codigo,
    )
    return {"items": items, "meta": meta}


@router.post(
    "",
    response_model=UnidadRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(create_unit_permission)],
)
def create_unidad(
    payload: UnidadCreate = Body(...), session: Session = Depends(get_session)
) -> UnidadRead:
    unidad = service.create(session, payload)
    return service.to_read(unidad, service.usage(session, unidad).model_dump())


@router.get(
    "/{item_id}",
    response_model=UnidadRead,
    dependencies=[Depends(read_units_permission)],
)
def get_unidad(
    item_id: UUID = Path(...), session: Session = Depends(get_session)
) -> UnidadRead:
    unidad = service.get(session, item_id)
    if unidad is None:
        raise HTTPException(status_code=404, detail=f"Unidad {item_id} no encontrada")
    return service.to_read(unidad, service.usage(session, unidad).model_dump())


@router.put(
    "/{item_id}",
    response_model=UnidadRead,
    dependencies=[Depends(update_unit_permission)],
)
def update_unidad(
    item_id: UUID = Path(...),
    payload: UnidadUpdate = Body(...),
    session: Session = Depends(get_session),
) -> UnidadRead:
    unidad = service.update(session, item_id, payload)
    if unidad is None:
        raise HTTPException(status_code=404, detail=f"Unidad {item_id} no encontrada")
    return service.to_read(unidad, service.usage(session, unidad).model_dump())


@router.delete(
    "/{item_id}",
    response_model=UnidadRead,
    dependencies=[Depends(deactivate_unit_permission)],
)
def deactivate_unidad(
    item_id: UUID = Path(...), session: Session = Depends(get_session)
) -> UnidadRead:
    unidad = service.deactivate(session, item_id)
    if unidad is None:
        raise HTTPException(status_code=404, detail=f"Unidad {item_id} no encontrada")
    return service.to_read(unidad, service.usage(session, unidad).model_dump())


@router.post(
    "/{item_id}/reactivar",
    response_model=UnidadRead,
    dependencies=[Depends(reactivate_unit_permission)],
)
def reactivate_unidad(
    item_id: UUID = Path(...), session: Session = Depends(get_session)
) -> UnidadRead:
    unidad = service.reactivate(session, item_id)
    if unidad is None:
        raise HTTPException(status_code=404, detail=f"Unidad {item_id} no encontrada")
    return service.to_read(unidad, service.usage(session, unidad).model_dump())