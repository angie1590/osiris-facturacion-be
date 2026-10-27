from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.core.catalog_permissions import catalog_permission
from osiris.modules.inventario.categoria_atributo.models import (
    CategoriaAtributoRead,
)
from osiris.modules.inventario.categoria_atributo.service import CategoriaAtributoService


router = APIRouter(prefix="/api/v1/categorias-atributos", tags=["Categorías de Atributos"])
service = CategoriaAtributoService()
read_category_attributes_permission = catalog_permission("read_attributes")
LEGACY_WRITE_DISABLED = {
    "code": "LEGACY_CATEGORY_ATTRIBUTE_WRITE_DISABLED",
    "message": "Utilice las operaciones contextuales de la categoría.",
}
LEGACY_WRITE_DISABLED_DOC: dict[int | str, dict[str, Any]] = {
    410: {
        "description": "Las escrituras legacy están deshabilitadas; utilice las rutas contextuales.",
        "content": {"application/json": {"example": LEGACY_WRITE_DISABLED}},
    }
}


@router.get(
    "",
    response_model=list[CategoriaAtributoRead],
    deprecated=True,
    dependencies=[Depends(read_category_attributes_permission)],
)
def list_categoria_atributos(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    categoria_id: Optional[UUID] = Query(None),
    session: Session = Depends(get_session),
) -> list[CategoriaAtributoRead]:
    mappings = service.list_paginated(session, skip=skip, limit=limit, categoria_id=categoria_id)
    return [CategoriaAtributoRead.model_validate(mapping) for mapping in mappings]


@router.get(
    "/{id}",
    response_model=CategoriaAtributoRead,
    deprecated=True,
    dependencies=[Depends(read_category_attributes_permission)],
)
def get_categoria_atributo(id: UUID, session: Session = Depends(get_session)) -> CategoriaAtributoRead:
    mapping = service.get(session, id)
    if mapping is None:
        raise HTTPException(status_code=404, detail=f"Mapeo de atributo {id} no encontrado")
    return CategoriaAtributoRead.model_validate(mapping)


@router.post(
    "",
    status_code=410,
    deprecated=True,
    responses=LEGACY_WRITE_DISABLED_DOC,
)
def create_categoria_atributo() -> JSONResponse:
    return JSONResponse(status_code=410, content=LEGACY_WRITE_DISABLED)


@router.put(
    "/{id}",
    status_code=410,
    deprecated=True,
    responses=LEGACY_WRITE_DISABLED_DOC,
)
def update_categoria_atributo(id: UUID) -> JSONResponse:
    _ = id
    return JSONResponse(status_code=410, content=LEGACY_WRITE_DISABLED)


@router.delete(
    "/{id}",
    status_code=410,
    deprecated=True,
    responses=LEGACY_WRITE_DISABLED_DOC,
)
def delete_categoria_atributo(id: UUID) -> JSONResponse:
    _ = id
    return JSONResponse(status_code=410, content=LEGACY_WRITE_DISABLED)
