from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1/categorias-atributos", tags=["Categorías de Atributos"])
LEGACY_READ_DISABLED = {
    "code": "LEGACY_CATEGORY_ATTRIBUTE_READ_DISABLED",
    "message": "Utilice las rutas contextuales de categorías y atributos.",
}
LEGACY_READ_DISABLED_DOC: dict[int | str, dict[str, Any]] = {
    410: {
        "description": "La lectura legacy está deshabilitada; utilice las rutas contextuales.",
        "content": {"application/json": {"example": LEGACY_READ_DISABLED}},
    }
}
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


@router.get("", status_code=410, deprecated=True, responses=LEGACY_READ_DISABLED_DOC)
def list_categoria_atributos() -> JSONResponse:
    return JSONResponse(status_code=410, content=LEGACY_READ_DISABLED)


@router.get("/{id}", status_code=410, deprecated=True, responses=LEGACY_READ_DISABLED_DOC)
def get_categoria_atributo(id: UUID) -> JSONResponse:
    _ = id
    return JSONResponse(status_code=410, content=LEGACY_READ_DISABLED)


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
