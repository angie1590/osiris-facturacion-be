from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from osiris.core.auth import get_current_usuario
from osiris.core.company_scope import ensure_entity_belongs_to_selected_company, resolve_company_scope
from osiris.core.db import get_session
from osiris.domain.schemas import PaginatedResponse
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.rol.entity import Rol
from osiris.modules.common.usuario.entity import Usuario
from osiris.modules.inventario.producto.entity import Producto
from osiris.modules.sri.impuesto_catalogo.entity import TipoImpuesto
from osiris.utils.pagination import build_pagination_meta
from .entity import MedidaTributariaProducto, MedidaTributariaTemporal
from .models import (
    MedidaProductoRead,
    MedidaTributariaCambioEstado,
    MedidaTributariaCreate,
    MedidaTributariaRead,
    MedidaTributariaUpdate,
)
from .service import MedidaTributariaService


router = APIRouter(prefix="/api/v1/medidas-tributarias-temporales", tags=["Medidas tributarias temporales"])
service = MedidaTributariaService()


def _require_admin(usuario: Usuario, session: Session) -> None:
    rol = session.get(Rol, usuario.rol_id)
    normalized = (rol.nombre if rol else "").strip().casefold()
    if normalized not in {"admin", "administrador", "administradora"}:
        raise HTTPException(status_code=403, detail="Solo administradores pueden gestionar medidas tributarias.")


def _read_measure(session: Session, measure: MedidaTributariaTemporal) -> MedidaTributariaRead:
    empresa = session.get(Empresa, measure.empresa_id)
    targets = list(
        session.exec(
            select(MedidaTributariaProducto).where(
                MedidaTributariaProducto.medida_id == measure.id,
                MedidaTributariaProducto.activo == True,  # noqa: E712
            )
        ).all()
    )
    products = []
    for target in targets:
        producto = session.get(Producto, target.producto_id)
        products.append(
            MedidaProductoRead(
                producto_id=target.producto_id,
                producto_nombre=producto.nombre if producto else "Producto no disponible",
                factor_cantidad=target.factor_cantidad,
                unidad_gravable=target.unidad_gravable,
            )
        )
    return MedidaTributariaRead(
        id=measure.id,
        empresa_id=measure.empresa_id,
        empresa_nombre=empresa.razon_social if empresa else None,
        nombre=measure.nombre,
        referencia_legal=measure.referencia_legal,
        tipo_impuesto=TipoImpuesto(measure.tipo_impuesto),
        componente=measure.componente,
        fecha_inicio=measure.fecha_inicio,
        fecha_fin=measure.fecha_fin,
        codigo_impuesto_sri=measure.codigo_impuesto_sri,
        codigo_porcentaje_sri=measure.codigo_porcentaje_sri,
        codigo_sri_confirmado=measure.codigo_sri_confirmado,
        tarifa=measure.tarifa,
        estado=measure.estado,
        productos=products,
        creado_en=measure.creado_en,
        actualizado_en=measure.actualizado_en,
    )


@router.get("", response_model=PaginatedResponse[MedidaTributariaRead])
def listar_medidas(
    empresa_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    usuario: Usuario = Depends(get_current_usuario),
    session: Session = Depends(get_session),
) -> PaginatedResponse[MedidaTributariaRead]:
    _require_admin(usuario, session)
    scoped_empresa_id = resolve_company_scope(requested_company_id=empresa_id)
    items, total = service.list(session, empresa_id=scoped_empresa_id, limit=limit, offset=offset)
    return PaginatedResponse[MedidaTributariaRead](
        items=[_read_measure(session, item) for item in items],
        meta=build_pagination_meta(total=total, limit=limit, offset=offset),
    )


@router.get("/{measure_id}", response_model=MedidaTributariaRead)
def obtener_medida(
    measure_id: UUID,
    usuario: Usuario = Depends(get_current_usuario),
    session: Session = Depends(get_session),
) -> MedidaTributariaRead:
    _require_admin(usuario, session)
    measure = session.get(MedidaTributariaTemporal, measure_id)
    if not measure or not measure.activo:
        raise HTTPException(status_code=404, detail="Medida temporal no encontrada.")
    ensure_entity_belongs_to_selected_company(measure.empresa_id)
    return _read_measure(session, measure)


@router.post("", response_model=MedidaTributariaRead, status_code=201)
def crear_medida(
    payload: MedidaTributariaCreate,
    usuario: Usuario = Depends(get_current_usuario),
    session: Session = Depends(get_session),
) -> MedidaTributariaRead:
    _require_admin(usuario, session)
    empresa_id = resolve_company_scope(requested_company_id=payload.empresa_id)
    scoped_payload = payload.model_copy(update={"empresa_id": empresa_id, "usuario_auditoria": str(usuario.id)})
    created = service.create(session, scoped_payload)
    return _read_measure(session, created)


@router.put("/{measure_id}", response_model=MedidaTributariaRead)
def actualizar_medida(
    measure_id: UUID,
    payload: MedidaTributariaUpdate,
    usuario: Usuario = Depends(get_current_usuario),
    session: Session = Depends(get_session),
) -> MedidaTributariaRead:
    _require_admin(usuario, session)
    existing = session.get(MedidaTributariaTemporal, measure_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Medida temporal no encontrada.")
    ensure_entity_belongs_to_selected_company(existing.empresa_id)
    updated = service.update(
        session,
        measure_id,
        payload.model_copy(update={"usuario_auditoria": str(usuario.id)}),
    )
    return _read_measure(session, updated)


@router.patch("/{measure_id}/estado", response_model=MedidaTributariaRead)
def cambiar_estado_medida(
    measure_id: UUID,
    payload: MedidaTributariaCambioEstado,
    usuario: Usuario = Depends(get_current_usuario),
    session: Session = Depends(get_session),
) -> MedidaTributariaRead:
    _require_admin(usuario, session)
    existing = session.get(MedidaTributariaTemporal, measure_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Medida temporal no encontrada.")
    ensure_entity_belongs_to_selected_company(existing.empresa_id)
    updated = service.set_state(session, measure_id, payload.estado, actor=str(usuario.id))
    return _read_measure(session, updated)
