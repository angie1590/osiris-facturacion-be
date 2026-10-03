from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.core.auth import require_roles
from osiris.domain.schemas import PaginatedResponse
from osiris.modules.inventario.categoria.models import (
    CategoriaCreate,
    CategoriaRead,
    CategoriaUpdate,
    RecategorizarProductosRequest,
)
from osiris.modules.inventario.categoria.service import CategoriaService


router = APIRouter(prefix="/api/v1/categorias", tags=["Categorías"])
service = CategoriaService()


@router.get("", response_model=PaginatedResponse[CategoriaRead])
def list_categorias(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    only_active: bool = Query(True),
    session: Session = Depends(get_session),
) -> PaginatedResponse[CategoriaRead]:
    items, meta = service.list_paginated(session, only_active=only_active, limit=limit, offset=offset)
    return PaginatedResponse[CategoriaRead].model_validate({"items": items, "meta": meta})


@router.get("/sin-clasificar/conteo")
def contar_sin_recategorizar(session: Session = Depends(get_session)) -> dict[str, int]:
    return {"count": service.contar_productos_sin_recategorizar(session)}


@router.get("/sin-clasificar/productos")
def listar_sin_recategorizar(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return service.listar_productos_sin_recategorizar(session)


@router.post("/recategorizar", dependencies=[Depends(require_roles("admin", "supervisor"))])
def recategorizar_productos(
    payload: RecategorizarProductosRequest,
    session: Session = Depends(get_session),
) -> dict[str, int]:
    return service.recategorizar_productos(session, payload.assignments)


@router.get("/{item_id}", response_model=CategoriaRead)
def get_categoria(
    item_id: UUID = Path(...),
    session: Session = Depends(get_session),
) -> CategoriaRead:
    obj = service.get(session, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"Categoría {item_id} not found")
    return CategoriaRead.model_validate(obj)


@router.post("", response_model=CategoriaRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_roles("admin", "supervisor"))])
def create_categoria(
    payload: CategoriaCreate = Body(...),
    session: Session = Depends(get_session),
) -> CategoriaRead:
    return CategoriaRead.model_validate(service.create(session, payload.model_dump(exclude_unset=True)))


@router.put("/{item_id}", response_model=CategoriaRead, dependencies=[Depends(require_roles("admin", "supervisor"))])
def update_categoria(
    item_id: UUID = Path(...),
    payload: CategoriaUpdate = Body(...),
    session: Session = Depends(get_session),
) -> CategoriaRead:
    updated = service.update(session, item_id, payload.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Categoría {item_id} not found")
    return CategoriaRead.model_validate(updated)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_roles("admin", "supervisor"))])
def delete_categoria(
    item_id: UUID = Path(...),
    confirmar_baja_productos: bool = Query(False),
    session: Session = Depends(get_session),
) -> None:
    ok = service.delete(session, item_id, confirmar_baja_productos=confirmar_baja_productos)
    if ok is None:
        raise HTTPException(status_code=404, detail=f"Categoría {item_id} not found")
