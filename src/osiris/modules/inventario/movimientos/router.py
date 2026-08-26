from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.modules.inventario.movimientos.schemas import (
    KardexResponse,
    MovimientoInventarioAnularRequest,
    MovimientoInventarioConfirmRequest,
    MovimientoInventarioCreate,
    MovimientoInventarioRead,
    TransferenciaInventarioCreate,
    TransferenciaInventarioRead,
    ValoracionResponse,
)
from osiris.modules.inventario.movimientos.services.movimiento_inventario_service import MovimientoInventarioService


COMMON_RESPONSES = {
    400: {"description": "Solicitud inválida para la operación de inventario."},
    404: {"description": "Recurso no encontrado."},
}

router = APIRouter(prefix="/api/v1/inventarios", tags=["Movimientos de Inventario"])
service = MovimientoInventarioService()


@router.post(
    "/movimientos",
    response_model=MovimientoInventarioRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear movimiento de inventario",
    responses=COMMON_RESPONSES,
)
def crear_movimiento_borrador(payload: MovimientoInventarioCreate, session: Session = Depends(get_session)):
    """Crea un movimiento en estado borrador sin afectar saldos hasta su confirmación."""
    movimiento = service.crear_movimiento_borrador(session, payload)
    return service.obtener_movimiento_read(session, movimiento.id)


@router.post(
    "/movimientos/{movimiento_id}/confirmar",
    response_model=MovimientoInventarioRead,
    summary="Confirmar movimiento de inventario",
    responses=COMMON_RESPONSES,
)
def confirmar_movimiento(
    movimiento_id: UUID,
    payload: MovimientoInventarioConfirmRequest,
    session: Session = Depends(get_session),
):
    """Confirma el movimiento aplicando locks, regla anti-negativos y valoración NIIF."""
    movimiento = service.confirmar_movimiento(
        session,
        movimiento_id,
        motivo_ajuste=payload.motivo_ajuste,
        usuario_autorizador=payload.usuario_auditoria,
    )
    return service.obtener_movimiento_read(session, movimiento.id)


@router.post(
    "/movimientos/{movimiento_id}/anular",
    response_model=MovimientoInventarioRead,
    summary="Anular movimiento de inventario",
    responses=COMMON_RESPONSES,
)
def anular_movimiento(
    movimiento_id: UUID,
    payload: MovimientoInventarioAnularRequest,
    session: Session = Depends(get_session),
):
    """Anula movimiento con reverso automático de stock cuando el original está confirmado."""
    movimiento = service.anular_movimiento(
        session,
        movimiento_id,
        motivo=payload.motivo,
        usuario_autorizador=payload.usuario_auditoria,
    )
    return service.obtener_movimiento_read(session, movimiento.id)


@router.post(
    "/transferencias",
    response_model=TransferenciaInventarioRead,
    status_code=status.HTTP_201_CREATED,
    summary="Transferir inventario entre bodegas",
    responses=COMMON_RESPONSES,
)
def transferir_entre_bodegas(
    payload: TransferenciaInventarioCreate,
    session: Session = Depends(get_session),
):
    """Ejecuta una transferencia atómica: egreso en origen + ingreso en destino."""
    return service.transferir_entre_bodegas(session, payload)


@router.get("/kardex", response_model=KardexResponse, summary="Consultar kardex operativo", responses=COMMON_RESPONSES)
def obtener_kardex(
    producto_id: UUID = Query(...),
    bodega_id: UUID = Query(...),
    fecha_inicio: date | None = Query(default=None),
    fecha_fin: date | None = Query(default=None),
    session: Session = Depends(get_session),
):
    """Retorna movimientos cronológicos del producto en bodega con saldos acumulados."""
    return service.obtener_kardex(
        session,
        producto_id=producto_id,
        bodega_id=bodega_id,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )


@router.get("/valoracion", response_model=ValoracionResponse, summary="Consultar valoración de inventario", responses=COMMON_RESPONSES)
def obtener_valoracion(session: Session = Depends(get_session)):
    """Devuelve la valoración de inventario por bodega y total global a costo promedio vigente."""
    return service.obtener_valoracion(session)
