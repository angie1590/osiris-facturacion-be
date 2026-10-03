from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.core.auth import require_roles
from osiris.modules.inventario.categoria_atributo.models import (
    CategoriaAtributoCreate,
    CategoriaAtributoRead,
    CategoriaAtributoUpdate,
)
from osiris.modules.inventario.categoria_atributo.service import CategoriaAtributoService


router = APIRouter(prefix="/api/v1/categorias-atributos", tags=["Categorías de Atributos"])
service = CategoriaAtributoService()


@router.get("", response_model=list[CategoriaAtributoRead])
def list_categoria_atributos(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    categoria_id: Optional[UUID] = Query(None),
    session: Session = Depends(get_session),
) -> list[CategoriaAtributoRead]:
    mappings = service.list_paginated(session, skip=skip, limit=limit, categoria_id=categoria_id)
    return [CategoriaAtributoRead.model_validate(mapping) for mapping in mappings]


@router.get("/{id}", response_model=CategoriaAtributoRead)
def get_categoria_atributo(id: UUID, session: Session = Depends(get_session)) -> CategoriaAtributoRead:
    mapping = service.get(session, id)
    if mapping is None:
        raise HTTPException(status_code=404, detail=f"Mapeo de atributo {id} no encontrado")
    return CategoriaAtributoRead.model_validate(mapping)


@router.post("", response_model=CategoriaAtributoRead, status_code=201, dependencies=[Depends(require_roles("admin", "supervisor"))])
def create_categoria_atributo(
    dto: CategoriaAtributoCreate,
    session: Session = Depends(get_session),
) -> CategoriaAtributoRead:
    mapping = service.create(session, dto, usuario_auditoria="api")
    return CategoriaAtributoRead.model_validate(mapping)


@router.put("/{id}", response_model=CategoriaAtributoRead, dependencies=[Depends(require_roles("admin", "supervisor"))])
def update_categoria_atributo(
    id: UUID,
    dto: CategoriaAtributoUpdate,
    session: Session = Depends(get_session),
) -> CategoriaAtributoRead:
    mapping = service.update(session, id, dto, usuario_auditoria="api")
    if mapping is None:
        raise HTTPException(status_code=404, detail=f"Mapeo de atributo {id} no encontrado")
    return CategoriaAtributoRead.model_validate(mapping)


@router.delete("/{id}", status_code=204, dependencies=[Depends(require_roles("admin", "supervisor"))])
def delete_categoria_atributo(id: UUID, session: Session = Depends(get_session)) -> None:
    service.delete(session, id, usuario_auditoria="api")
