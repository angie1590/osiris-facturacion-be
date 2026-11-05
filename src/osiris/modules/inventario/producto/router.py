from __future__ import annotations

from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.core.product_permissions import (
    create_product_permission,
    delete_product_permission,
    read_product_permission,
    update_product_permission,
)
from osiris.domain.schemas import PaginatedResponse
from osiris.modules.inventario.producto.models import (
    ProductoCompletoRead,
    ProductoCambioCategoriaPreviewInput,
    ProductoCambioCategoriaPreviewResponse,
    ProductoIntegralCreate,
    ProductoIntegralUpdate,
    ProductoListadoRead,
)
from osiris.modules.inventario.producto.service import ProductoService
from osiris.modules.inventario.producto.category_preview import (
    preview_product_category_change,
)
from osiris.modules.inventario.producto_impuesto.service import ProductoImpuestoService
from osiris.modules.inventario.producto.entity import TipoProducto
from osiris.modules.sri.impuesto_catalogo.models import ImpuestoCatalogoRead
from osiris.modules.common.proveedor_persona.entity import ProveedorPersona
from osiris.modules.common.proveedor_sociedad.entity import ProveedorSociedad
from osiris.modules.common.usuario.entity import Usuario


router = APIRouter(prefix="/api/v1/productos", tags=["Productos"])
service = ProductoService()
producto_impuesto_service = ProductoImpuestoService()


class ProveedoresProductoRequest(BaseModel):
    proveedor_ids: List[UUID]


@router.get(
    "/impuestos-disponibles",
    response_model=list[ImpuestoCatalogoRead],
    dependencies=[Depends(read_product_permission)],
)
def listar_impuestos_disponibles(
    tipo_producto: TipoProducto,
    session: Session = Depends(get_session),
) -> list[ImpuestoCatalogoRead]:
    impuestos = producto_impuesto_service.listar_impuestos_permitidos(session, tipo_producto)
    return [ImpuestoCatalogoRead.model_validate(impuesto) for impuesto in impuestos]


@router.get(
    "",
    response_model=PaginatedResponse[ProductoListadoRead],
    dependencies=[Depends(read_product_permission)],
)
def list_productos(
    limit: int = Query(50, ge=1, le=1000, description="Máximo de registros a devolver"),
    offset: int = Query(0, ge=0, description="Número de registros a saltar"),
    only_active: bool = Query(True, description="Filtrar por activo=True/False"),
    session: Session = Depends(get_session),
) -> PaginatedResponse[ProductoListadoRead]:
    items, meta = service.list_paginated_completo(session, only_active=only_active, limit=limit, offset=offset)
    return PaginatedResponse[ProductoListadoRead].model_validate({"items": items, "meta": meta})


@router.get(
    "/{producto_id}",
    response_model=ProductoCompletoRead,
    dependencies=[Depends(read_product_permission)],
)
def get_producto(producto_id: UUID, session: Session = Depends(get_session)) -> ProductoCompletoRead:
    return ProductoCompletoRead.model_validate(service.get_producto_completo(session, producto_id))


@router.post("", response_model=ProductoCompletoRead, status_code=201)
def create_producto(
    payload: ProductoIntegralCreate,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(create_product_permission),
) -> ProductoCompletoRead:
    producto = service.create_integral(session, payload, actor_id=usuario.id)
    return ProductoCompletoRead.model_validate(service.get_producto_completo(session, producto.id))


@router.put("/{producto_id}", response_model=ProductoCompletoRead)
def update_producto(
    producto_id: UUID,
    payload: ProductoIntegralUpdate,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(update_product_permission),
) -> ProductoCompletoRead:
    producto = service.update_integral(
        session,
        producto_id,
        payload,
        actor_id=usuario.id,
    )
    if not producto:
        raise HTTPException(status_code=404, detail=f"Producto {producto_id} no encontrado")
    return ProductoCompletoRead.model_validate(service.get_producto_completo(session, producto_id))


@router.post(
    "/{producto_id}/previsualizar-cambio-categoria",
    response_model=ProductoCambioCategoriaPreviewResponse,
    dependencies=[Depends(update_product_permission)],
)
def previsualizar_cambio_categoria_producto(
    producto_id: UUID,
    payload: ProductoCambioCategoriaPreviewInput,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(update_product_permission),
) -> ProductoCambioCategoriaPreviewResponse:
    return preview_product_category_change(
        session,
        producto_id,
        payload,
        actor_id=usuario.id,
    )


@router.delete(
    "/{producto_id}",
    status_code=204,
    dependencies=[Depends(delete_product_permission)],
)
def delete_producto(producto_id: UUID, session: Session = Depends(get_session)) -> None:
    service.delete(session, producto_id)
    return None


@router.put(
    "/{producto_id}/atributos",
    status_code=410,
    dependencies=[Depends(update_product_permission)],
)
def legacy_upsert_producto_atributos(
    producto_id: UUID,
    payload: Any = Body(...),
) -> None:
    raise HTTPException(
        status_code=410,
        detail={
            "code": "LEGACY_PRODUCT_WRITE_DISABLED",
            "message": "Utilice el contrato integral de Producto.",
        },
    )


def _set_proveedores(
    session: Session,
    producto_id: UUID,
    provider_ids: List[UUID],
    model: Any,
    setter: Any,
) -> None:
    if not service.get(session, producto_id):
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    providers = session.exec(select(model).where(model.id.in_(provider_ids), model.activo.is_(True))).all()
    if len(providers) != len(set(provider_ids)):
        raise HTTPException(status_code=404, detail="Uno o más proveedores no existen o están inactivos")
    setter(session, producto_id, provider_ids)
    session.commit()


@router.put(
    "/{producto_id}/proveedores-persona",
    dependencies=[Depends(update_product_permission)],
)
def asignar_proveedores_persona(
    producto_id: UUID,
    payload: ProveedoresProductoRequest,
    session: Session = Depends(get_session),
) -> ProductoCompletoRead:
    _set_proveedores(session, producto_id, payload.proveedor_ids, ProveedorPersona, service.repo.set_proveedores_persona)
    return ProductoCompletoRead.model_validate(service.get_producto_completo(session, producto_id))


@router.put(
    "/{producto_id}/proveedores-sociedad",
    dependencies=[Depends(update_product_permission)],
)
def asignar_proveedores_sociedad(
    producto_id: UUID,
    payload: ProveedoresProductoRequest,
    session: Session = Depends(get_session),
) -> ProductoCompletoRead:
    _set_proveedores(session, producto_id, payload.proveedor_ids, ProveedorSociedad, service.repo.set_proveedores_sociedad)
    return ProductoCompletoRead.model_validate(service.get_producto_completo(session, producto_id))
