from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from osiris.core.db import get_session
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
):
    return service.list_paginated(session, skip=skip, limit=limit, categoria_id=categoria_id)


@router.get("/{id}", response_model=CategoriaAtributoRead)
def get_categoria_atributo(id: UUID, session: Session = Depends(get_session)):
    return service.get(session, id)


@router.post("", response_model=CategoriaAtributoRead, status_code=201)
def create_categoria_atributo(dto: CategoriaAtributoCreate, session: Session = Depends(get_session)):
    return service.create(session, dto, usuario_auditoria="api")


@router.put("/{id}", response_model=CategoriaAtributoRead)
def update_categoria_atributo(id: UUID, dto: CategoriaAtributoUpdate, session: Session = Depends(get_session)):
    return service.update(session, id, dto, usuario_auditoria="api")


@router.delete("/{id}", status_code=204)
def delete_categoria_atributo(id: UUID, session: Session = Depends(get_session)):
    service.delete(session, id, usuario_auditoria="api")
