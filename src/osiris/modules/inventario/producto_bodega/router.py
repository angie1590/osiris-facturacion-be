from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.modules.inventario.producto_bodega.models import (
    ProductoBodegaAsignarRequest,
    ProductoBodegaRead,
    ProductoBodegaUpdate,
    StockDisponibleRead,
)
from osiris.modules.inventario.producto_bodega.service import ProductoBodegaService


COMMON_RESPONSES = {
    400: {"description": "Solicitud inválida para la operación de inventario."},
    404: {"description": "Recurso no encontrado."},
    409: {"description": "Conflicto de negocio o recurso inactivo."},
}

router = APIRouter(tags=["Producto-Bodega"])
service = ProductoBodegaService()


@router.post(
    "/api/v1/productos/{producto_id}/bodegas/{bodega_id}",
    response_model=ProductoBodegaRead,
    status_code=status.HTTP_201_CREATED,
    summary="Asignar producto a bodega",
    responses=COMMON_RESPONSES,
)
def asignar_producto_a_bodega(
    producto_id: UUID,
    bodega_id: UUID,
    payload: ProductoBodegaAsignarRequest,
    session: Session = Depends(get_session),
):
    """Crea la relación producto-bodega validando bodega activa y reglas de fracciones."""
    return service.create(
        session,
        {
            "producto_id": producto_id,
            "bodega_id": bodega_id,
            "cantidad": payload.cantidad,
            "usuario_auditoria": payload.usuario_auditoria,
        },
    )


@router.put(
    "/api/v1/productos/{producto_id}/bodegas/{bodega_id}",
    response_model=ProductoBodegaRead,
    summary="Actualizar cantidad de producto en bodega",
    responses=COMMON_RESPONSES,
)
def actualizar_cantidad_producto_bodega(
    producto_id: UUID,
    bodega_id: UUID,
    payload: ProductoBodegaUpdate,
    session: Session = Depends(get_session),
):
    """Actualiza (o crea) la cantidad de un producto en una bodega."""
    return service.update_cantidad(
        session,
        producto_id=producto_id,
        bodega_id=bodega_id,
        cantidad=payload.cantidad if payload.cantidad is not None else 0,
        usuario_auditoria=payload.usuario_auditoria,
    )


@router.get(
    "/api/v1/productos/{producto_id}/bodegas",
    summary="Listar bodegas asignadas a un producto",
    responses=COMMON_RESPONSES,
)
def listar_bodegas_por_producto(
    producto_id: UUID,
    session: Session = Depends(get_session),
):
    """Devuelve el inventario referencial del producto por bodega activa."""
    return service.get_bodegas_by_producto(session, producto_id)


@router.get(
    "/api/v1/bodegas/{bodega_id}/productos",
    summary="Listar productos asignados a una bodega",
    responses=COMMON_RESPONSES,
)
def listar_productos_por_bodega(
    bodega_id: UUID,
    session: Session = Depends(get_session),
):
    """Devuelve los productos activos asignados a la bodega."""
    return service.get_productos_by_bodega(session, bodega_id)


@router.get(
    "/api/v1/inventarios/stock-disponible",
    response_model=list[StockDisponibleRead],
    summary="Consultar stock disponible (lectura optimizada)",
    responses=COMMON_RESPONSES,
)
def consultar_stock_disponible(
    producto_id: UUID | None = Query(default=None),
    bodega_id: UUID | None = Query(default=None),
    session: Session = Depends(get_session),
):
    """Consulta rápida de stock por producto/bodega para reducir carga de consultas complejas."""
    return service.get_stock_disponible(
        session,
        producto_id=producto_id,
        bodega_id=bodega_id,
    )

