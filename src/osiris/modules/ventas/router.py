from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.domain.schemas import PaginatedResponse
from osiris.modules.sri.facturacion_electronica.services.fe_mapper_service import FEMapperService
from osiris.modules.sri.core_sri.models import (
    EstadoCuentaPorCobrar,
    EstadoRetencionRecibida,
    EstadoVenta,
    TipoEmisionVenta,
)
from osiris.modules.ventas.schemas import (
    CuentaPorCobrarListItemRead,
    CuentaPorCobrarRead,
    FEPayloadRead,
    PagoCxCCreate,
    PagoCxCRead,
    RetencionRecibidaAnularRequest,
    RetencionRecibidaCreate,
    RetencionRecibidaListItemRead,
    RetencionRecibidaRead,
    VentaAnularRequest,
    VentaCreate,
    VentaEmitRequest,
    VentaListItemRead,
    VentaRead,
    VentaRegistroCreate,
    VentaUpdate,
)
from osiris.modules.ventas.services.cxc_service import CuentaPorCobrarService
from osiris.modules.ventas.services.retencion_recibida_service import RetencionRecibidaService
from osiris.modules.ventas.services.venta_service import VentaService


COMMON_RESPONSES = {
    400: {"description": "Solicitud inválida para la regla de negocio."},
    404: {"description": "Recurso no encontrado."},
}

router = APIRouter()
ventas_router = APIRouter(prefix="/api/v1/ventas", tags=["Ventas"])
retenciones_router = APIRouter(prefix="/api/v1/retenciones-recibidas", tags=["Retenciones Recibidas"])
cxc_router = APIRouter(prefix="/api/v1/cxc", tags=["Cuentas por Cobrar"])

venta_service = VentaService()
fe_mapper_service = FEMapperService()
retencion_recibida_service = RetencionRecibidaService()
cxc_service = CuentaPorCobrarService()


@ventas_router.post("", response_model=VentaRead, status_code=status.HTTP_201_CREATED, summary="Registrar venta", responses=COMMON_RESPONSES)
def crear_venta(
    payload: VentaCreate,
    background_tasks: BackgroundTasks,
    emitir_automaticamente: bool = Query(default=True),
    session: Session = Depends(get_session),
):
    venta = venta_service.registrar_venta(session, payload)
    if emitir_automaticamente:
        venta = venta_service.emitir_venta(
            session,
            venta.id,
            usuario_auditoria=payload.usuario_auditoria,
            background_tasks=background_tasks,
            encolar_sri=True,
        )
    return venta_service.obtener_venta_read(session, venta.id)


@ventas_router.get("", response_model=PaginatedResponse[VentaListItemRead], summary="Listar ventas", responses=COMMON_RESPONSES)
def listar_ventas(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    only_active: bool = Query(True),
    fecha_inicio: date | None = Query(default=None),
    fecha_fin: date | None = Query(default=None),
    estado: EstadoVenta | None = Query(default=None),
    tipo_emision: TipoEmisionVenta | None = Query(default=None),
    texto: str | None = Query(default=None, min_length=1),
    session: Session = Depends(get_session),
):
    items, meta = venta_service.listar_ventas(
        session,
        limit=limit,
        offset=offset,
        only_active=only_active,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        estado=estado,
        tipo_emision=tipo_emision,
        texto=texto,
    )
    return {"items": items, "meta": meta}


@ventas_router.post("/desde-productos", response_model=VentaRead, status_code=status.HTTP_201_CREATED, summary="Registrar venta desde catálogo", responses=COMMON_RESPONSES)
def crear_venta_desde_productos(
    payload: VentaRegistroCreate,
    background_tasks: BackgroundTasks,
    emitir_automaticamente: bool = Query(default=True),
    session: Session = Depends(get_session),
):
    venta = venta_service.registrar_venta_desde_productos(session, payload)
    if emitir_automaticamente:
        venta = venta_service.emitir_venta(
            session,
            venta.id,
            usuario_auditoria=payload.usuario_auditoria,
            background_tasks=background_tasks,
            encolar_sri=True,
        )
    return venta_service.obtener_venta_read(session, venta.id)


@ventas_router.put("/{venta_id}", response_model=VentaRead, summary="Actualizar venta", responses=COMMON_RESPONSES)
def actualizar_venta(venta_id: UUID, payload: VentaUpdate, session: Session = Depends(get_session)):
    venta = venta_service.actualizar_venta(session, venta_id, payload)
    return venta_service.obtener_venta_read(session, venta.id)


@ventas_router.patch("/{venta_id}", response_model=VentaRead, summary="Actualizar venta parcialmente", responses=COMMON_RESPONSES)
def actualizar_venta_parcial(venta_id: UUID, payload: VentaUpdate, session: Session = Depends(get_session)):
    venta = venta_service.actualizar_venta(session, venta_id, payload)
    return venta_service.obtener_venta_read(session, venta.id)


@ventas_router.get("/{venta_id}", response_model=VentaRead, summary="Obtener venta por ID", responses=COMMON_RESPONSES)
def obtener_venta(venta_id: UUID, session: Session = Depends(get_session)):
    return venta_service.obtener_venta_read(session, venta_id)


@ventas_router.post("/{venta_id}/emitir", response_model=VentaRead, summary="Emitir venta", responses=COMMON_RESPONSES)
def emitir_venta(venta_id: UUID, payload: VentaEmitRequest, background_tasks: BackgroundTasks, session: Session = Depends(get_session)):
    venta = venta_service.emitir_venta(
        session,
        venta_id,
        usuario_auditoria=payload.usuario_auditoria,
        background_tasks=background_tasks,
        encolar_sri=True,
    )
    return venta_service.obtener_venta_read(session, venta.id)


@ventas_router.post("/{venta_id}/anular", response_model=VentaRead, summary="Anular venta", responses=COMMON_RESPONSES)
def anular_venta(venta_id: UUID, payload: VentaAnularRequest, session: Session = Depends(get_session)):
    venta = venta_service.anular_venta(
        session,
        venta_id,
        usuario_auditoria=payload.usuario_auditoria,
        confirmado_portal_sri=payload.confirmado_portal_sri,
        motivo=payload.motivo,
    )
    return venta_service.obtener_venta_read(session, venta.id)


@ventas_router.get("/{venta_id}/fe-payload", response_model=FEPayloadRead, summary="Obtener payload FE-EC de venta", responses=COMMON_RESPONSES)
def obtener_payload_fe_venta(venta_id: UUID, session: Session = Depends(get_session)):
    venta = venta_service.obtener_venta_read(session, venta_id)
    return fe_mapper_service.venta_to_fe_payload(venta)


@retenciones_router.post("", response_model=RetencionRecibidaRead, status_code=status.HTTP_201_CREATED, summary="Registrar retención recibida", responses=COMMON_RESPONSES)
def crear_retencion_recibida(payload: RetencionRecibidaCreate, session: Session = Depends(get_session)):
    return retencion_recibida_service.crear_retencion_recibida(session, payload)


@retenciones_router.get("", response_model=PaginatedResponse[RetencionRecibidaListItemRead], summary="Listar retenciones recibidas", responses=COMMON_RESPONSES)
def listar_retenciones_recibidas(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    only_active: bool = Query(True),
    fecha_inicio: date | None = Query(default=None),
    fecha_fin: date | None = Query(default=None),
    estado: EstadoRetencionRecibida | None = Query(default=None),
    session: Session = Depends(get_session),
):
    items, meta = retencion_recibida_service.listar_retenciones_recibidas(
        session,
        limit=limit,
        offset=offset,
        only_active=only_active,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        estado=estado,
    )
    return {"items": items, "meta": meta}


@retenciones_router.get("/{retencion_id}", response_model=RetencionRecibidaRead, summary="Obtener retención recibida por ID", responses=COMMON_RESPONSES)
def obtener_retencion_recibida(retencion_id: UUID, session: Session = Depends(get_session)):
    return retencion_recibida_service.obtener_retencion_recibida_read(session, retencion_id)


@retenciones_router.post("/{retencion_id}/anular", response_model=RetencionRecibidaRead, summary="Anular retención recibida", responses=COMMON_RESPONSES)
def anular_retencion_recibida(retencion_id: UUID, payload: RetencionRecibidaAnularRequest, session: Session = Depends(get_session)):
    return retencion_recibida_service.anular_retencion_recibida(
        session,
        retencion_id,
        motivo=payload.motivo,
        usuario_auditoria=payload.usuario_auditoria,
    )


@retenciones_router.post("/{retencion_id}/aplicar", response_model=RetencionRecibidaRead, summary="Aplicar retención recibida", responses=COMMON_RESPONSES)
def aplicar_retencion_recibida(retencion_id: UUID, session: Session = Depends(get_session)):
    return retencion_recibida_service.aplicar_retencion_recibida(session, retencion_id)


@cxc_router.get("/{venta_id}", response_model=CuentaPorCobrarRead, summary="Obtener cuenta por cobrar de venta", responses=COMMON_RESPONSES)
def obtener_cxc_por_venta(venta_id: UUID, session: Session = Depends(get_session)):
    return cxc_service.obtener_cxc_por_venta(session, venta_id)


@cxc_router.get("", response_model=PaginatedResponse[CuentaPorCobrarListItemRead], summary="Listar cuentas por cobrar", responses=COMMON_RESPONSES)
def listar_cxc(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    only_active: bool = Query(True),
    estado: EstadoCuentaPorCobrar | None = Query(default=None),
    texto: str | None = Query(default=None, min_length=1),
    session: Session = Depends(get_session),
):
    items, meta = cxc_service.listar_cxc(
        session,
        limit=limit,
        offset=offset,
        only_active=only_active,
        estado=estado,
        texto=texto,
    )
    return {"items": items, "meta": meta}


@cxc_router.post("/{venta_id}/pagos", response_model=PagoCxCRead, status_code=status.HTTP_201_CREATED, summary="Registrar pago de CxC", responses=COMMON_RESPONSES)
def registrar_pago_cxc(venta_id: UUID, payload: PagoCxCCreate, session: Session = Depends(get_session)):
    cxc = cxc_service.obtener_cxc_por_venta(session, venta_id)
    return cxc_service.registrar_pago_cxc(session, cxc.id, payload)


router.include_router(ventas_router)
router.include_router(retenciones_router)
router.include_router(cxc_router)
