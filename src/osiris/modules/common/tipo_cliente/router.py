from __future__ import annotations

from uuid import UUID
from typing import Any, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.core.directory_permissions import directory_permission
from osiris.domain.schemas import PaginatedResponse
from osiris.modules.common.tipo_cliente.models import (
    TipoClienteCreate,
    TipoClienteRead,
    TipoClienteUpdate,
)
from osiris.modules.common.tipo_cliente.service import TipoClienteService

router = APIRouter(prefix="/api/v1/tipos-cliente", tags=["Tipos de Cliente"])
service = TipoClienteService()


@router.get(
    "",
    response_model=PaginatedResponse[TipoClienteRead],
    dependencies=[Depends(directory_permission("TIPOS_CLIENTE", "leer"))],
)
def list_tipos_cliente(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    only_active: bool = Query(True),
    q: str | None = Query(None),
    estado: Literal["activo", "inactivo"] | None = Query(None),
    sort_by: str = Query("creado_en"),
    sort_direction: Literal["asc", "desc"] = Query("desc"),
    sort_order: Literal["asc", "desc"] | None = Query(None),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    items, meta = service.list_paginated(
        session,
        only_active=only_active,
        limit=limit,
        offset=offset,
        q=q,
        estado=estado,
        sort_by=sort_by,
        sort_direction=sort_direction,
        sort_order=sort_order,
    )
    return {"items": items, "meta": meta}


@router.get(
    "/{item_id}",
    response_model=TipoClienteRead,
    dependencies=[Depends(directory_permission("TIPOS_CLIENTE", "leer"))],
)
def get_tipo_cliente(
    item_id: UUID = Path(...), session: Session = Depends(get_session)
) -> Any:
    obj = service.get(session, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"Tipo-cliente {item_id} not found")
    return obj


@router.post(
    "",
    response_model=TipoClienteRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(directory_permission("TIPOS_CLIENTE", "crear"))],
)
def create_tipo_cliente(
    payload: TipoClienteCreate = Body(...), session: Session = Depends(get_session)
) -> Any:
    return service.create(session, payload.model_dump(exclude_unset=True))


@router.put(
    "/{item_id}",
    response_model=TipoClienteRead,
    dependencies=[Depends(directory_permission("TIPOS_CLIENTE", "actualizar"))],
)
def update_tipo_cliente(
    item_id: UUID = Path(...),
    payload: TipoClienteUpdate = Body(...),
    session: Session = Depends(get_session),
) -> Any:
    updated = service.update(session, item_id, payload.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Tipo-cliente {item_id} not found")
    return updated


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(directory_permission("TIPOS_CLIENTE", "eliminar"))],
)
def delete_tipo_cliente(
    item_id: UUID = Path(...), session: Session = Depends(get_session)
) -> None:
    ok = service.delete(session, item_id)
    if ok is None:
        raise HTTPException(status_code=404, detail=f"Tipo-cliente {item_id} not found")


@router.post(
    "/{item_id}/reactivar",
    response_model=TipoClienteRead,
    dependencies=[Depends(directory_permission("TIPOS_CLIENTE", "actualizar"))],
)
def reactivate_tipo_cliente(
    item_id: UUID, session: Session = Depends(get_session)
) -> Any:
    return service.to_read(session, service.reactivate(session, item_id))
