from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.core.auth import require_roles
from osiris.domain.schemas import PaginatedResponse
from osiris.modules.inventario.atributo.models import AtributoCreate, AtributoRead, AtributoUpdate
from osiris.modules.inventario.atributo.service import AtributoService
from osiris.modules.inventario.atributo.remap_service import AtributoRemapeoService
from osiris.modules.inventario.producto.models_atributos import ProductoAtributoRemapeoResolve


router = APIRouter(prefix="/api/v1/atributos", tags=["Atributos"])
service = AtributoService()
remap_service = AtributoRemapeoService()


@router.get("/remapeos/pendientes", dependencies=[Depends(require_roles("admin", "supervisor"))])
def listar_remapeos_pendientes(session: Session = Depends(get_session)) -> dict[str, Any]:
    return remap_service.listar_pendientes(session)


@router.post("/remapeos/resolver", dependencies=[Depends(require_roles("admin", "supervisor"))])
def resolver_remapeos(
    assignments: list[ProductoAtributoRemapeoResolve],
    session: Session = Depends(get_session),
) -> dict[str, int]:
    return remap_service.resolver(session, assignments)


@router.get("", response_model=PaginatedResponse[AtributoRead])
def list_atributos(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    only_active: bool = Query(True),
    session: Session = Depends(get_session),
) -> PaginatedResponse[AtributoRead]:
    items, meta = service.list_paginated(session, only_active=only_active, limit=limit, offset=offset)
    return PaginatedResponse[AtributoRead].model_validate({"items": items, "meta": meta})


@router.get("/{item_id}", response_model=AtributoRead)
def get_atributo(
    item_id: UUID = Path(...),
    session: Session = Depends(get_session),
) -> AtributoRead:
    obj = service.get(session, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"Atributo {item_id} not found")
    return AtributoRead.model_validate(obj)


@router.post("", response_model=AtributoRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_roles("admin", "supervisor"))])
def create_atributo(
    payload: AtributoCreate = Body(...),
    session: Session = Depends(get_session),
) -> AtributoRead:
    return AtributoRead.model_validate(service.create(session, payload.model_dump(exclude_unset=True)))


@router.put("/{item_id}", response_model=AtributoRead, dependencies=[Depends(require_roles("admin", "supervisor"))])
def update_atributo(
    item_id: UUID = Path(...),
    payload: AtributoUpdate = Body(...),
    session: Session = Depends(get_session),
) -> AtributoRead:
    updated = service.update(session, item_id, payload.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Atributo {item_id} not found")
    return AtributoRead.model_validate(updated)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_roles("admin", "supervisor"))])
def delete_atributo(item_id: UUID = Path(...), session: Session = Depends(get_session)) -> None:
    ok = service.delete(session, item_id)
    if ok is None:
        raise HTTPException(status_code=404, detail=f"Atributo {item_id} not found")
