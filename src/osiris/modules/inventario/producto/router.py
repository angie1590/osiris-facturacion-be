from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.domain.schemas import PaginatedResponse
from osiris.modules.inventario.producto.models import (
    ProductoCompletoRead,
    ProductoCreate,
    ProductoListadoRead,
    ProductoUpdate,
)
from osiris.modules.inventario.producto.models_atributos import (
    ProductoAtributoValorRead,
    ProductoAtributoValorUpsert,
)
from osiris.modules.inventario.producto.service import ProductoService
from osiris.modules.inventario.producto.service_atributos import ProductoAtributoValorService


router = APIRouter(prefix="/api/v1/productos", tags=["Productos"])
service = ProductoService()
atributo_valor_service = ProductoAtributoValorService()


@router.get("", response_model=PaginatedResponse[ProductoListadoRead])
def list_productos(
    limit: int = Query(50, ge=1, le=1000, description="Máximo de registros a devolver"),
    offset: int = Query(0, ge=0, description="Número de registros a saltar"),
    only_active: bool = Query(True, description="Filtrar por activo=True/False"),
    session: Session = Depends(get_session),
):
    items, meta = service.list_paginated_completo(session, only_active=only_active, limit=limit, offset=offset)
    return {"items": items, "meta": meta}


@router.get("/{producto_id}", response_model=ProductoCompletoRead)
def get_producto(producto_id: UUID, session: Session = Depends(get_session)):
    return service.get_producto_completo(session, producto_id)


@router.post("", response_model=ProductoCompletoRead, status_code=201)
def create_producto(payload: ProductoCreate, session: Session = Depends(get_session)):
    producto = service.create(session, payload.model_dump(exclude_unset=True))
    return service.get_producto_completo(session, producto.id)


@router.put("/{producto_id}", response_model=ProductoCompletoRead)
def update_producto(producto_id: UUID, payload: ProductoUpdate, session: Session = Depends(get_session)):
    producto = service.update(session, producto_id, payload.model_dump(exclude_unset=True))
    if not producto:
        raise HTTPException(status_code=404, detail=f"Producto {producto_id} no encontrado")
    return service.get_producto_completo(session, producto_id)


@router.delete("/{producto_id}", status_code=204)
def delete_producto(producto_id: UUID, session: Session = Depends(get_session)):
    service.delete(session, producto_id)
    return None


@router.put(
    "/{producto_id}/atributos",
    response_model=list[ProductoAtributoValorRead],
    status_code=200,
    responses={
        400: {
            "description": (
                "Error de validacion de aplicabilidad o tipo de dato. "
                "Ejemplos: atributo no aplicable a la categoria actual, "
                "o valor incompatible con el tipo esperado."
            )
        }
    },
)
def upsert_producto_atributos(
    producto_id: UUID,
    payload: list[ProductoAtributoValorUpsert],
    session: Session = Depends(get_session),
):
    entities = atributo_valor_service.upsert_valores_producto_validando_aplicabilidad(session, producto_id, payload)
    return [ProductoAtributoValorRead.model_validate(item) for item in entities]
