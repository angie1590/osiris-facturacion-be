from __future__ import annotations

from uuid import UUID
from typing import Any, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.core.directory_permissions import directory_permission
from osiris.domain.schemas import PaginatedResponse
from osiris.modules.common.proveedor_sociedad.models import (
    ProveedorSociedadCreate,
    ProveedorSociedadRead,
    ProveedorSociedadUpdate,
)
from osiris.modules.common.proveedor_sociedad.service import ProveedorSociedadService

router = APIRouter(prefix="/api/v1/proveedores-sociedad", tags=["Proveedores Sociedad"])
service = ProveedorSociedadService()


@router.get(
    "",
    response_model=PaginatedResponse[ProveedorSociedadRead],
    dependencies=[Depends(directory_permission("PROVEEDORES_SOCIEDAD", "leer"))],
)
def list_proveedores_sociedad(
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
    response_model=ProveedorSociedadRead,
    dependencies=[Depends(directory_permission("PROVEEDORES_SOCIEDAD", "leer"))],
)
def get_proveedor_sociedad(
    item_id: UUID = Path(...), session: Session = Depends(get_session)
) -> Any:
    obj = service.get(session, item_id)
    if not obj:
        raise HTTPException(
            status_code=404, detail=f"Proveedor-sociedad {item_id} not found"
        )
    return service.to_read(session, obj)


@router.post(
    "",
    response_model=ProveedorSociedadRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(directory_permission("PROVEEDORES_SOCIEDAD", "crear"))],
)
def create_proveedor_sociedad(
    payload: ProveedorSociedadCreate = Body(...),
    session: Session = Depends(get_session),
) -> Any:
    return service.to_read(
        session, service.create(session, payload.model_dump(exclude_unset=True))
    )


@router.put(
    "/{item_id}",
    response_model=ProveedorSociedadRead,
    dependencies=[Depends(directory_permission("PROVEEDORES_SOCIEDAD", "actualizar"))],
)
def update_proveedor_sociedad(
    item_id: UUID = Path(...),
    payload: ProveedorSociedadUpdate = Body(...),
    session: Session = Depends(get_session),
) -> Any:
    updated = service.update(session, item_id, payload.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Proveedor-sociedad {item_id} not found"
        )
    return service.to_read(session, updated)


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(directory_permission("PROVEEDORES_SOCIEDAD", "eliminar"))],
)
def delete_proveedor_sociedad(
    item_id: UUID = Path(...), session: Session = Depends(get_session)
) -> None:
    ok = service.delete(session, item_id)
    if ok is None:
        raise HTTPException(
            status_code=404, detail=f"Proveedor-sociedad {item_id} not found"
        )


@router.post(
    "/{item_id}/reactivar",
    response_model=ProveedorSociedadRead,
    dependencies=[Depends(directory_permission("PROVEEDORES_SOCIEDAD", "actualizar"))],
)
def reactivate_proveedor_sociedad(
    item_id: UUID, session: Session = Depends(get_session)
) -> Any:
    return service.to_read(session, service.reactivate(session, item_id))
