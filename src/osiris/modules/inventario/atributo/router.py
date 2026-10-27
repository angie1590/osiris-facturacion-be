from __future__ import annotations

from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from sqlmodel import Session, col, select

from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION, get_session
from osiris.core.auth import require_roles
from osiris.core.catalog_permissions import catalog_permission
from osiris.domain.catalog_contracts import (
    Confirmation,
    ImpactItem,
    LifecycleInput,
    PreviewResponse,
)
from osiris.domain.schemas import PaginatedResponse
from osiris.modules.inventario.atributo.models import (
    AtributoCreateEnCategoria,
    AtributoRead,
    AtributoUnidadRead,
    AtributoUpdate,
)
from osiris.modules.inventario.atributo.entity import Atributo
from osiris.modules.inventario.atributo.service import AtributoService
from osiris.modules.inventario.atributo.remap_service import AtributoRemapeoService
from osiris.modules.common.unidad.entity import Unidad
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.inventario.categoria_atributo.service import CategoriaAtributoService
from osiris.modules.inventario.categoria.service import CategoriaService
from osiris.modules.inventario.categoria.b3_preview import b3_preview_signer
from osiris.modules.common.usuario.entity import Usuario
from osiris.utils.attribute_code import generate_attribute_code
from osiris.modules.inventario.producto.models_atributos import (
    ProductoAtributoRemapeoResolve,
)

router = APIRouter(prefix="/api/v1/atributos", tags=["Atributos"])
service = AtributoService()
remap_service = AtributoRemapeoService()
create_and_assign_attribute_permission = catalog_permission(
    "create_and_assign_attribute"
)
read_attributes_permission = catalog_permission("read_attributes")
preview_attribute_update_permission = catalog_permission("preview_attribute_update")
deactivate_attribute_permission = catalog_permission("deactivate_attribute")
preview_attribute_deactivation_permission = catalog_permission(
    "preview_attribute_deactivation"
)
undo_attribute_change_permission = catalog_permission("undo_attribute_change")
reactivate_attribute_permission = catalog_permission("reactivate_attribute")
update_attribute_permission = catalog_permission("update_attribute")
category_attribute_service = CategoriaAtributoService()


def _new_category_attribute_preview_state(
    session: Session, payload: AtributoCreateEnCategoria
) -> tuple[dict[str, Any], list[UUID], list[UUID], dict[UUID, str], UUID, dict[str, Any]]:
    code = generate_attribute_code(payload.nombre)
    provisional_id = uuid5(
        NAMESPACE_URL,
        f"osiris:attribute-preview:{payload.categoria_id}:{code}",
    )
    proposed_attribute = Atributo(
        id=provisional_id,
        nombre=payload.nombre,
        codigo=code,
        tipo_dato=payload.tipo_dato,
        unidad_id=payload.unidad_id,
        select_options=payload.select_options,
        catalog_id=payload.catalog_id,
        allow_negative=payload.allow_negative,
        min_value=payload.min_value,
        max_value=payload.max_value,
        activo=True,
    )
    if payload.valor_default is not None:
        category_attribute_service._validate_default(
            session, proposed_attribute, payload.valor_default
        )
    proposed_mapping = CategoriaAtributo(
        categoria_id=payload.categoria_id,
        atributo_id=provisional_id,
        orden=payload.orden,
        obligatorio=payload.obligatorio,
        valor_default=payload.valor_default,
        activo=False,
    )
    state, affected, missing, names = category_attribute_service.required_attribute_impact(
        session, proposed_mapping, proposed=True, proposed_attribute=proposed_attribute
    )
    normalized_payload = payload.model_dump(
        mode="json",
        exclude_unset=True,
        exclude={"precondicion_preview", "usuario_auditoria"},
    )
    return state, affected, missing, names, provisional_id, normalized_payload


def _serialize_attributes_with_units(
    attributes: list[Any], session: Session
) -> list[AtributoRead]:
    unit_ids = {attribute.unidad_id for attribute in attributes if attribute.unidad_id}
    units = {
        unit.id: unit
        for unit in session.exec(
            select(Unidad).where(col(Unidad.id).in_(unit_ids))
        ).all()
    } if unit_ids else {}
    return [
        AtributoRead.model_validate(
            attribute,
            update={
                "unidad": (
                    AtributoUnidadRead.model_validate(units[attribute.unidad_id])
                    if attribute.unidad_id in units
                    else None
                )
            },
        )
        for attribute in attributes
    ]


def _attribute_update_preview_payload(payload: AtributoUpdate) -> dict[str, Any]:
    return payload.model_dump(
        mode="json",
        exclude_unset=True,
        exclude={
            "precondicion_preview",
            "confirmar_anotacion_unidad",
            "usuario_auditoria",
        },
    )


def _include_annotation_unit_state(
    session: Session,
    state: dict[str, Any],
    unit_id: UUID | None,
    *,
    lock: bool = False,
) -> dict[str, Any]:
    unit = None
    if unit_id is not None:
        statement = (
            select(Unidad)
            .where(col(Unidad.id) == unit_id)
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        )
        if lock:
            statement = statement.with_for_update()
        unit = session.exec(statement).first()
    state["unidad_anotacion"] = (
        {
            "id": str(unit.id),
            "codigo": unit.codigo,
            "simbolo": unit.simbolo,
            "magnitud_codigo": unit.magnitud_codigo,
            "activo": unit.activo,
        }
        if unit is not None
        else None
    )
    return state


@router.get(
    "/remapeos/pendientes", dependencies=[Depends(require_roles("admin", "supervisor"))]
)
def listar_remapeos_pendientes(
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return remap_service.listar_pendientes(session)


@router.post(
    "/remapeos/resolver", dependencies=[Depends(require_roles("admin", "supervisor"))]
)
def resolver_remapeos(
    assignments: list[ProductoAtributoRemapeoResolve],
    session: Session = Depends(get_session),
) -> dict[str, int]:
    return remap_service.resolver(session, assignments)


@router.get(
    "",
    response_model=PaginatedResponse[AtributoRead],
    dependencies=[Depends(read_attributes_permission)],
)
def list_atributos(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    only_active: bool = Query(True),
    session: Session = Depends(get_session),
) -> PaginatedResponse[AtributoRead]:
    items, meta = service.list_paginated(
        session, only_active=only_active, limit=limit, offset=offset
    )
    return PaginatedResponse[AtributoRead](
        items=_serialize_attributes_with_units(items, session), meta=meta
    )


@router.get(
    "/{item_id}",
    response_model=AtributoRead,
    dependencies=[Depends(read_attributes_permission)],
)
def get_atributo(
    item_id: UUID = Path(...),
    session: Session = Depends(get_session),
) -> AtributoRead:
    obj = service.get(session, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"Atributo {item_id} not found")
    return _serialize_attributes_with_units([obj], session)[0]


@router.post(
    "/{item_id}/previsualizar",
)
def preview_atributo(
    item_id: UUID = Path(...),
    payload: AtributoUpdate = Body(...),
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(preview_attribute_update_permission),
) -> dict[str, Any]:
    result = service.preview_update(
        session,
        item_id,
        payload.model_dump(
            exclude_unset=True,
            exclude={"precondicion_preview", "confirmar_anotacion_unidad"},
        ),
    )
    if result is None:
        raise HTTPException(status_code=404, detail=f"Atributo {item_id} not found")
    annotation = result.get("unidad_anotacion")
    if annotation is not None:
        attribute = service.repo.get(session, item_id)
        if attribute is None:
            raise HTTPException(status_code=404, detail=f"Atributo {item_id} not found")
        state, _ = service._capture_unit_annotation_state(session, attribute)
        state = _include_annotation_unit_state(
            session, state, payload.unidad_id
        )
        token = b3_preview_signer().issue(
            operation="ANNOTATE_ATTRIBUTE_UNIT",
            target=f"/api/v1/atributos/{item_id}",
            actor=str(usuario.id),
            payload=_attribute_update_preview_payload(payload),
            state=state,
        )
        annotation["precondicion_preview"] = token
        result["precondicion_preview"] = token
    return result


@router.get(
    "/{item_id}/reversion",
    dependencies=[Depends(read_attributes_permission)],
)
def get_atributo_lifecycle(
    item_id: UUID = Path(...), session: Session = Depends(get_session)
) -> dict[str, Any]:
    result = service.lifecycle_status(session, item_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Atributo {item_id} not found")
    return result


@router.post(
    "/{item_id}/revertir",
    dependencies=[Depends(undo_attribute_change_permission)],
)
def undo_atributo(
    item_id: UUID = Path(...), session: Session = Depends(get_session)
) -> dict[str, Any]:
    result = service.undo(session, item_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Atributo {item_id} not found")
    return result


@router.post(
    "/{item_id}/reactivar",
    dependencies=[Depends(reactivate_attribute_permission)],
)
def reactivar_atributo(
    item_id: UUID = Path(...), session: Session = Depends(get_session)
) -> dict[str, Any]:
    result = service.reactivate(session, item_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Atributo {item_id} not found")
    return result


@router.post(
    "/{item_id}/previsualizar-baja",
    response_model=PreviewResponse,
    dependencies=[Depends(preview_attribute_deactivation_permission)],
)
def previsualizar_baja_atributo(
    item_id: UUID = Path(...),
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(preview_attribute_deactivation_permission),
) -> PreviewResponse:
    attribute = service.repo.get(session, item_id)
    if attribute is None:
        raise HTTPException(status_code=404, detail=f"Atributo {item_id} not found")
    state = service._capture_state(session, attribute)
    active_values = [value for value in state["valores"] if value["activo"]]
    active_assignments = [
        assignment for assignment in state["asignaciones"] if assignment["activo"]
    ]
    pending_remaps = [remap for remap in state["remapeos"] if remap["activo"]]
    token = b3_preview_signer().issue(
        operation="DEACTIVATE_ATTRIBUTE",
        target=f"/api/v1/atributos/{item_id}",
        actor=str(usuario.id),
        payload={"confirmar": True},
        state=state,
    )
    return PreviewResponse(
        operacion="DEACTIVATE_ATTRIBUTE",
        resumen=(
            f"La baja global desactivará {len(active_assignments)} asignaciones y "
            f"{len(active_values)} valores EAV activos."
        ),
        conteos={
            "asignaciones_activas": len(active_assignments),
            "valores_activos": len(active_values),
            "remapeos_pendientes": len(pending_remaps),
        },
        faltantes=[],
        conversiones=[],
        incompatibles=[],
        remapeos=[
            ImpactItem(
                id=UUID(remap["id"]),
                nombre=f"Producto {remap['producto_id']}",
                motivo=remap["motivo"],
            )
            for remap in pending_remaps
        ],
        cambio_unidad=None,
        requiere_confirmacion=True,
        acciones_permitidas=(
            ["resolver_remapeos", "cancelar"]
            if pending_remaps
            else ["confirmar", "cancelar"]
        ),
        precondicion_preview=token,
    )


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(deactivate_attribute_permission)],
)
def delete_atributo(
    item_id: UUID = Path(...),
    payload: Confirmation[LifecycleInput] = Body(...),
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(deactivate_attribute_permission),
) -> None:
    if payload.payload.confirmar is not True:
        raise HTTPException(status_code=422, detail="La baja requiere confirmación explícita.")
    from osiris.modules.inventario.categoria.service import CategoriaService

    CategoriaService.acquire_hierarchy_mutation_lock(session)
    attribute = service.repo.get(session, item_id)
    if attribute is None:
        raise HTTPException(status_code=404, detail=f"Atributo {item_id} not found")
    state = service._capture_state(session, attribute, lock=True)
    b3_preview_signer().verify(
        payload.precondicion_preview,
        operation="DEACTIVATE_ATTRIBUTE",
        target=f"/api/v1/atributos/{item_id}",
        actor=str(usuario.id),
        payload=payload.payload.model_dump(mode="json"),
        state=state,
    )
    result = service.delete(session, item_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Atributo {item_id} not found")


@router.post(
    "/previsualizar",
    response_model=PreviewResponse,
    dependencies=[Depends(create_and_assign_attribute_permission)],
)
def previsualizar_creacion_atributo_en_categoria(
    payload: AtributoCreateEnCategoria = Body(...),
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(create_and_assign_attribute_permission),
) -> PreviewResponse:
    category = session.get(Categoria, payload.categoria_id)
    if category is None or not category.activo:
        raise HTTPException(status_code=404, detail="Categoría no encontrada o inactiva.")
    state, affected, missing, product_names, _, normalized_payload = (
        _new_category_attribute_preview_state(session, payload)
    )
    token = b3_preview_signer().issue(
        operation="CREATE_AND_ASSIGN_ATTRIBUTE",
        target="/api/v1/atributos",
        actor=str(usuario.id),
        payload=normalized_payload,
        state=state,
    )
    return PreviewResponse(
        operacion="CREATE_AND_ASSIGN_ATTRIBUTE",
        resumen=(
            f"{len(missing)} de {len(affected)} productos activos carecen de un valor válido."
            if missing
            else f"No hay faltantes entre {len(affected)} productos activos afectados."
        ),
        conteos={
            "productos_afectados": len(affected),
            "productos_faltantes": len(missing),
        },
        faltantes=[
            ImpactItem(
                id=product_id,
                nombre=product_names.get(product_id, "Producto"),
                motivo="No tiene un valor EAV activo válido para este atributo.",
            )
            for product_id in missing
        ],
        conversiones=[],
        incompatibles=[],
        remapeos=[],
        cambio_unidad=None,
        requiere_confirmacion=(payload.obligatorio or payload.aplicar_default_a_existentes),
        acciones_permitidas=(
            ["aplicar_default", "proporcionar_valores", "cancelar"]
            if missing
            else ["confirmar", "cancelar"]
        ),
        precondicion_preview=token,
    )


@router.post(
    "",
    response_model=AtributoRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(create_and_assign_attribute_permission)],
)
def create_atributo(
    payload: AtributoCreateEnCategoria = Body(...),
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(create_and_assign_attribute_permission),
) -> AtributoRead:
    data = payload.model_dump(
        exclude_unset=True,
        exclude={"precondicion_preview", "usuario_auditoria"},
    )
    data["usuario_auditoria"] = str(usuario.id)
    if payload.obligatorio or payload.aplicar_default_a_existentes:
        CategoriaService.acquire_hierarchy_mutation_lock(session)
        token = payload.precondicion_preview
        if not token:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "CATALOG_PREVIEW_STALE",
                    "message": "Previsualiza la creación y asignación antes de confirmarla.",
                    "conteos": {},
                    "acciones_permitidas": ["previsualizar"],
                },
            )
        state, _, _, _, _, normalized_payload = _new_category_attribute_preview_state(
            session, payload
        )
        b3_preview_signer().verify(
            token,
            operation="CREATE_AND_ASSIGN_ATTRIBUTE",
            target="/api/v1/atributos",
            actor=str(usuario.id),
            payload=normalized_payload,
            state=state,
        )
    created = service.create_for_category(session, data)
    return _serialize_attributes_with_units([created], session)[0]


@router.put(
    "/{item_id}",
    response_model=AtributoRead,
)
def update_atributo(
    item_id: UUID = Path(...),
    payload: AtributoUpdate = Body(...),
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(update_attribute_permission),
) -> AtributoRead:
    values = payload.model_dump(
        exclude_unset=True,
        exclude={"precondicion_preview", "confirmar_anotacion_unidad"},
    )
    allow_unit_annotation = False
    if payload.confirmar_anotacion_unidad:
        if not payload.precondicion_preview:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "ATTRIBUTE_UNIT_ANNOTATION_REQUIRES_CONFIRMATION",
                    "message": "Previsualiza la anotación y confirma su interpretación antes de guardar.",
                    "conteos": {},
                    "acciones_permitidas": ["previsualizar", "cancelar"],
                },
            )
        CategoriaService.acquire_hierarchy_mutation_lock(session)
        attribute = session.exec(
            select(Atributo).where(col(Atributo.id) == item_id).with_for_update()
        ).first()
        if attribute is None:
            raise HTTPException(status_code=404, detail=f"Atributo {item_id} not found")
        state, _ = service._capture_unit_annotation_state(
            session, attribute, lock=True
        )
        state = _include_annotation_unit_state(
            session, state, payload.unidad_id, lock=True
        )
        b3_preview_signer().verify(
            payload.precondicion_preview,
            operation="ANNOTATE_ATTRIBUTE_UNIT",
            target=f"/api/v1/atributos/{item_id}",
            actor=str(usuario.id),
            payload=_attribute_update_preview_payload(payload),
            state=state,
        )
        allow_unit_annotation = True
    updated = service.update(
        session,
        item_id,
        values,
        allow_unit_annotation=allow_unit_annotation,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Atributo {item_id} not found")
    return _serialize_attributes_with_units([updated], session)[0]


