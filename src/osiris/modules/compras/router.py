from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.domain.schemas import PaginatedResponse
from osiris.modules.compras.schemas import (
    CompraAnularRequest,
    CompraCreate,
    CuentaPorPagarListItemRead,
    CuentaPorPagarRead,
    CompraRead,
    CompraRegistroCreate,
    CompraUpdate,
    GuardarPlantillaRetencionRequest,
    PagoCxPCreate,
    PagoCxPRead,
    PlantillaRetencionRead,
    RetencionCreate,
    RetencionEmitRequest,
    RetencionFEPayloadRead,
    RetencionRead,
    RetencionSugeridaRead,
)
from osiris.modules.sri.core_sri.models import EstadoCuentaPorPagar
from osiris.modules.compras.services.compra_service import CompraService
from osiris.modules.compras.services.cxp_service import CuentaPorPagarService
from osiris.modules.compras.services.retencion_service import RetencionService


COMMON_RESPONSES = {
    400: {"description": "Solicitud inválida para la regla de negocio."},
    404: {"description": "Recurso no encontrado."},
}

router = APIRouter()
compras_router = APIRouter(prefix="/api/v1/compras", tags=["Compras"])
retenciones_router = APIRouter(prefix="/api/v1/retenciones", tags=["Retenciones Emitidas"])
cxp_router = APIRouter(prefix="/api/v1/cxp", tags=["Cuentas por Pagar"])

compra_service = CompraService()
retencion_service = RetencionService()
cxp_service = CuentaPorPagarService()


@compras_router.post("", response_model=CompraRead, status_code=status.HTTP_201_CREATED, summary="Registrar compra", responses=COMMON_RESPONSES)
def crear_compra(payload: CompraCreate, session: Session = Depends(get_session)):
    return compra_service.registrar_compra(session, payload)


@compras_router.post("/desde-productos", response_model=CompraRead, status_code=status.HTTP_201_CREATED, summary="Registrar compra desde catálogo", responses=COMMON_RESPONSES)
def crear_compra_desde_productos(payload: CompraRegistroCreate, session: Session = Depends(get_session)):
    return compra_service.registrar_compra_desde_productos(session, payload)


@compras_router.put("/{compra_id}", response_model=CompraRead, summary="Actualizar compra", responses=COMMON_RESPONSES)
def actualizar_compra(compra_id: UUID, payload: CompraUpdate, session: Session = Depends(get_session)):
    return compra_service.actualizar_compra(session, compra_id, payload)


@compras_router.post("/{compra_id}/anular", response_model=CompraRead, summary="Anular compra", responses=COMMON_RESPONSES)
def anular_compra(compra_id: UUID, payload: CompraAnularRequest, session: Session = Depends(get_session)):
    return compra_service.anular_compra(session, compra_id, payload)


@compras_router.get("/{compra_id}/sugerir-retencion", response_model=RetencionSugeridaRead, summary="Sugerir retención", responses=COMMON_RESPONSES)
def sugerir_retencion_compra(compra_id: UUID, session: Session = Depends(get_session)):
    return retencion_service.sugerir_retencion(session, compra_id)


@compras_router.post("/{compra_id}/guardar-plantilla-retencion", response_model=PlantillaRetencionRead, summary="Guardar plantilla de retención", responses=COMMON_RESPONSES)
def guardar_plantilla_retencion_desde_compra(
    compra_id: UUID,
    payload: GuardarPlantillaRetencionRequest,
    session: Session = Depends(get_session),
):
    return retencion_service.guardar_plantilla_desde_retencion_digitada(session, compra_id, payload)


@compras_router.post("/{compra_id}/retenciones", response_model=RetencionRead, status_code=status.HTTP_201_CREATED, summary="Registrar retención emitida", responses=COMMON_RESPONSES)
def crear_retencion_compra(
    compra_id: UUID,
    payload: RetencionCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    return retencion_service.crear_retencion(
        session,
        compra_id,
        payload,
        encolar_sri=True,
        background_tasks=background_tasks,
    )


@retenciones_router.post("/{retencion_id}/emitir", response_model=RetencionRead, summary="Emitir retención", responses=COMMON_RESPONSES)
def emitir_retencion(
    retencion_id: UUID,
    payload: RetencionEmitRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    return retencion_service.emitir_retencion(session, retencion_id, payload, background_tasks=background_tasks)


@retenciones_router.get("/{retencion_id}/fe-payload", response_model=RetencionFEPayloadRead, summary="Obtener payload FE-EC de retención", responses=COMMON_RESPONSES)
def obtener_payload_fe_retencion(retencion_id: UUID, session: Session = Depends(get_session)):
    return retencion_service.obtener_payload_fe_retencion(session, retencion_id)


@cxp_router.get("", response_model=PaginatedResponse[CuentaPorPagarListItemRead], summary="Listar cuentas por pagar", responses=COMMON_RESPONSES)
def listar_cxp(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    only_active: bool = Query(True),
    estado: EstadoCuentaPorPagar | None = Query(default=None),
    texto: str | None = Query(default=None, min_length=1),
    session: Session = Depends(get_session),
):
    items, meta = cxp_service.listar_cxp(
        session,
        limit=limit,
        offset=offset,
        only_active=only_active,
        estado=estado,
        texto=texto,
    )
    return {"items": items, "meta": meta}


@cxp_router.get("/{compra_id}", response_model=CuentaPorPagarRead, summary="Obtener CxP por compra", responses=COMMON_RESPONSES)
def obtener_cxp_por_compra(compra_id: UUID, session: Session = Depends(get_session)):
    return cxp_service.obtener_cxp_por_compra(session, compra_id)


@cxp_router.post("/{compra_id}/pagos", response_model=PagoCxPRead, status_code=status.HTTP_201_CREATED, summary="Registrar pago de CxP", responses=COMMON_RESPONSES)
def registrar_pago_cxp(compra_id: UUID, payload: PagoCxPCreate, session: Session = Depends(get_session)):
    cxp = cxp_service.obtener_cxp_por_compra(session, compra_id)
    return cxp_service.registrar_pago_cxp(session, cxp.id, payload)


router.include_router(compras_router)
router.include_router(retenciones_router)
router.include_router(cxp_router)
