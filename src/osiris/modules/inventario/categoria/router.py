from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.domain.schemas import PaginatedResponse
from osiris.modules.inventario.categoria.models import CategoriaCreate, CategoriaRead, CategoriaUpdate
from osiris.modules.inventario.categoria.service import CategoriaService


router = APIRouter(prefix="/api/v1/categorias", tags=["Categorías"])
service = CategoriaService()


@router.get("", response_model=PaginatedResponse[CategoriaRead])
def list_categorias(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    only_active: bool = Query(True),
    session: Session = Depends(get_session),
):
    items, meta = service.list_paginated(session, only_active=only_active, limit=limit, offset=offset)
    return {"items": items, "meta": meta}


@router.get("/{item_id}", response_model=CategoriaRead)
def get_categoria(item_id: UUID = Path(...), session: Session = Depends(get_session)):
    obj = service.get(session, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"Categoría {item_id} not found")
    return obj


@router.post("", response_model=CategoriaRead, status_code=status.HTTP_201_CREATED)
def create_categoria(payload: CategoriaCreate = Body(...), session: Session = Depends(get_session)):
    return service.create(session, payload.model_dump(exclude_unset=True))


@router.put("/{item_id}", response_model=CategoriaRead)
def update_categoria(
    item_id: UUID = Path(...),
    payload: CategoriaUpdate = Body(...),
    session: Session = Depends(get_session),
):
    updated = service.update(session, item_id, payload.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Categoría {item_id} not found")
    return updated


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_categoria(item_id: UUID = Path(...), session: Session = Depends(get_session)):
    ok = service.delete(session, item_id)
    if ok is None:
        raise HTTPException(status_code=404, detail=f"Categoría {item_id} not found")
