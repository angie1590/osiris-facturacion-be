from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from sqlmodel import Session, col, select

from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION, get_session
from osiris.core.auth import require_roles
from osiris.core.catalog_permissions import catalog_permission
from osiris.domain.catalog_contracts import (
    AssignmentInput,
    CategoryTreeNode,
    ImpactItem,
    PreviewResponse,
    SelectableCategory,
)
from osiris.domain.schemas import PaginatedResponse
from osiris.modules.inventario.categoria.models import (
    CategoriaCreate,
    CategoriaB3CreateConfirmation,
    CategoriaB3UpdateConfirmation,
    CategoriaRead,
    CategoriaUpdate,
    CategoriaAtributoEfectivoRead,
    RecategorizarProductosRequest,
)
from osiris.modules.inventario.categoria.service import CategoriaService
from osiris.modules.inventario.categoria.b3_preview import (
    b3_preview_signer,
    b3_preview_state,
)
from osiris.modules.inventario.categoria.tree import (
    get_category_tree,
    get_selectable_categories,
)
from osiris.modules.inventario.categoria.resolver import (
    get_effective_attributes,
    get_own_attributes,
)
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria_atributo.service import (
    CategoriaAtributoService,
)
from osiris.modules.inventario.categoria_atributo.models import CategoriaAtributoUpdate
from osiris.modules.inventario.categoria_atributo.models import CategoriaAtributoRemoveConfirmation
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.common.usuario.entity import Usuario


router = APIRouter(prefix="/api/v1/categorias", tags=["Categorías"])
service = CategoriaService()
read_categories_permission = catalog_permission("read_categories")
create_category_permission = catalog_permission("create_category")
update_category_permission = catalog_permission("update_category")
deactivate_category_permission = catalog_permission("deactivate_category")
reactivate_category_permission = catalog_permission("reactivate_category")
read_category_attributes_permission = catalog_permission("read_category_attributes")
assign_category_attribute_permission = catalog_permission("assign_attribute")
category_attribute_service = CategoriaAtributoService()


def _b3_preview_response(
    session: Session,
    *,
    operation: str,
    target: str,
    actor_id: UUID,
    payload: dict[str, Any],
    parent_id: UUID | None,
    category_id: UUID | None = None,
) -> PreviewResponse:
    service._validate_parent(session, parent_id)
    state, product_ids = b3_preview_state(
        session, parent_id, category_id=category_id
    )
    token = b3_preview_signer().issue(
        operation=operation,
        target=target,
        actor=str(actor_id),
        payload=payload,
        state=state,
    )
    count = len(product_ids)
    return PreviewResponse(
        operacion=operation,
        resumen=(
            f"Se reclasificaran {count} productos directos bajo Sin clasificar."
            if count
            else "No hay productos directos que reclasificar."
        ),
        conteos={"productos_directos": count},
        faltantes=[],
        conversiones=[],
        incompatibles=[],
        remapeos=[],
        cambio_unidad=None,
        requiere_confirmacion=count > 0,
        acciones_permitidas=["confirmar", "cancelar"] if count else ["continuar"],
        precondicion_preview=token,
    )


def _verify_b3_confirmation(
    session: Session,
    *,
    operation: str,
    target: str,
    actor_id: UUID,
    payload: dict[str, Any],
    token: str,
    parent_id: UUID | None,
    category_id: UUID | None = None,
) -> None:
    CategoriaService.acquire_hierarchy_mutation_lock(session)
    state, product_ids = b3_preview_state(
        session, parent_id, category_id=category_id
    )
    b3_preview_signer().verify(
        token,
        operation=operation,
        target=target,
        actor=str(actor_id),
        payload=payload,
        state=state,
    )
    if not product_ids:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "CATALOG_PREVIEW_STALE",
                "message": "Los productos directos cambiaron; genera una nueva previsualizacion.",
                "conteos": {"productos_directos": 0},
                "acciones_permitidas": ["previsualizar"],
            },
        )


@router.get(
    "",
    response_model=PaginatedResponse[CategoriaRead],
    dependencies=[Depends(read_categories_permission)],
)
def list_categorias(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    only_active: bool = Query(True),
    session: Session = Depends(get_session),
) -> PaginatedResponse[CategoriaRead]:
    items, meta = service.list_paginated(session, only_active=only_active, limit=limit, offset=offset)
    return PaginatedResponse[CategoriaRead].model_validate({"items": items, "meta": meta})


@router.get(
    "/arbol",
    response_model=list[CategoryTreeNode],
    dependencies=[Depends(read_categories_permission)],
)
def get_arbol_categorias(
    session: Session = Depends(get_session),
) -> list[CategoryTreeNode]:
    return get_category_tree(session)


@router.get(
    "/seleccionables",
    response_model=list[SelectableCategory],
    dependencies=[Depends(read_categories_permission)],
)
def get_categorias_seleccionables(
    session: Session = Depends(get_session),
) -> list[SelectableCategory]:
    return [SelectableCategory.model_validate(item) for item in get_selectable_categories(session)]


def _read_category_attributes(
    session: Session, item_id: UUID, *, own_only: bool
) -> list[CategoriaAtributoEfectivoRead]:
    category = session.get(Categoria, item_id)
    if category is None or not category.activo:
        raise HTTPException(status_code=404, detail=f"Categoría {item_id} not found")
    resolved = (
        get_own_attributes(session, item_id)
        if own_only
        else get_effective_attributes(session, [item_id])
    )
    return [CategoriaAtributoEfectivoRead.model_validate(item) for item in resolved]


def _assignment_preview_mapping(
    session: Session, item_id: UUID, payload: AssignmentInput
) -> CategoriaAtributo:
    historical = session.exec(
        select(CategoriaAtributo)
        .where(
            col(CategoriaAtributo.categoria_id) == item_id,
            col(CategoriaAtributo.atributo_id) == payload.atributo_id,
        )
        .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
    ).first()
    if historical is not None and historical.activo:
        raise category_attribute_service._already_assigned()
    supplied = payload.model_dump(exclude_unset=True)
    mapping = CategoriaAtributo(
        categoria_id=item_id,
        atributo_id=payload.atributo_id,
        orden=supplied.get("orden", historical.orden if historical else None),
        obligatorio=supplied.get(
            "obligatorio", historical.obligatorio if historical else False
        ),
        valor_default=supplied.get(
            "valor_default", historical.valor_default if historical else None
        ),
        activo=False,
    )
    return mapping


@router.get(
    "/{item_id}/atributos-efectivos",
    response_model=list[CategoriaAtributoEfectivoRead],
    dependencies=[Depends(read_category_attributes_permission)],
)
def get_atributos_efectivos_categoria(
    item_id: UUID = Path(...), session: Session = Depends(get_session)
) -> list[CategoriaAtributoEfectivoRead]:
    return _read_category_attributes(session, item_id, own_only=False)


@router.get(
    "/{item_id}/atributos-propios",
    response_model=list[CategoriaAtributoEfectivoRead],
    dependencies=[Depends(read_category_attributes_permission)],
)
def get_atributos_propios_categoria(
    item_id: UUID = Path(...), session: Session = Depends(get_session)
) -> list[CategoriaAtributoEfectivoRead]:
    return _read_category_attributes(session, item_id, own_only=True)


@router.post(
    "/{item_id}/atributos",
    response_model=CategoriaAtributoEfectivoRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(assign_category_attribute_permission)],
)
def asignar_atributo_existente(
    item_id: UUID = Path(...),
    payload: AssignmentInput = Body(...),
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(assign_category_attribute_permission),
) -> CategoriaAtributoEfectivoRead:
    payload_data = payload.model_dump(
        mode="json", exclude_unset=True, exclude={"precondicion_preview"}
    )
    if payload.obligatorio is True or payload.aplicar_default_a_existentes:
        CategoriaService.acquire_hierarchy_mutation_lock(session)
        token = payload.precondicion_preview
        if not token:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "CATALOG_PREVIEW_STALE",
                    "message": "Previsualiza la asignación antes de aplicarla.",
                    "conteos": {},
                    "acciones_permitidas": ["previsualizar"],
                },
            )
        proposed = _assignment_preview_mapping(session, item_id, payload)
        state, _, _, _ = category_attribute_service.required_attribute_impact(
            session, proposed, proposed=True
        )
        b3_preview_signer().verify(
            token,
            operation="ASSIGN_CATEGORY_ATTRIBUTE",
            target=f"/api/v1/categorias/{item_id}/atributos",
            actor=str(usuario.id),
            payload=payload_data,
            state=state,
        )
    category_attribute_service.assign_existing(
        session,
        item_id,
        payload_data,
        usuario_auditoria=str(usuario.id),
    )
    effective = get_effective_attributes(session, [item_id])
    assigned = next(
        (item for item in effective if item["atributo_id"] == payload.atributo_id),
        None,
    )
    if assigned is None:
        raise HTTPException(status_code=409, detail="La asignación no quedó efectiva.")
    return CategoriaAtributoEfectivoRead.model_validate(assigned)


@router.post(
    "/{item_id}/atributos/previsualizar",
    response_model=PreviewResponse,
    dependencies=[Depends(assign_category_attribute_permission)],
)
def previsualizar_asignacion_atributo_existente(
    item_id: UUID = Path(...),
    payload: AssignmentInput = Body(...),
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(assign_category_attribute_permission),
) -> PreviewResponse:
    proposed = _assignment_preview_mapping(session, item_id, payload)
    state, affected_ids, missing_ids, product_names = (
        category_attribute_service.required_attribute_impact(
            session, proposed, proposed=True
        )
    )
    payload_data = payload.model_dump(
        mode="json", exclude_unset=True, exclude={"precondicion_preview"}
    )
    token = b3_preview_signer().issue(
        operation="ASSIGN_CATEGORY_ATTRIBUTE",
        target=f"/api/v1/categorias/{item_id}/atributos",
        actor=str(usuario.id),
        payload=payload_data,
        state=state,
    )
    return PreviewResponse(
        operacion="ASSIGN_CATEGORY_ATTRIBUTE",
        resumen=(
            f"{len(missing_ids)} de {len(affected_ids)} productos activos carecen de un valor válido."
            if missing_ids
            else f"No hay faltantes entre {len(affected_ids)} productos activos afectados."
        ),
        conteos={
            "productos_afectados": len(affected_ids),
            "productos_faltantes": len(missing_ids),
        },
        faltantes=[
            ImpactItem(
                id=product_id,
                nombre=product_names.get(product_id, "Producto"),
                motivo="No tiene un valor EAV activo válido para este atributo.",
            )
            for product_id in missing_ids
        ],
        conversiones=[],
        incompatibles=[],
        remapeos=[],
        cambio_unidad=None,
        requiere_confirmacion=(payload.obligatorio is True or payload.aplicar_default_a_existentes),
        acciones_permitidas=(
            ["aplicar_default", "proporcionar_valores", "cancelar"]
            if missing_ids
            else ["confirmar", "cancelar"]
        ),
        precondicion_preview=token,
    )


@router.put(
    "/{item_id}/atributos/{mapping_id}",
    response_model=CategoriaAtributoEfectivoRead,
    dependencies=[Depends(assign_category_attribute_permission)],
)
def actualizar_configuracion_atributo_categoria(
    item_id: UUID = Path(...),
    mapping_id: UUID = Path(...),
    payload: CategoriaAtributoUpdate = Body(...),
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(assign_category_attribute_permission),
) -> CategoriaAtributoEfectivoRead:
    mapping = session.get(CategoriaAtributo, mapping_id)
    if mapping is None or mapping.categoria_id != item_id or not mapping.activo:
        raise HTTPException(status_code=404, detail="Asignación no encontrada en la categoría.")
    if payload.obligatorio is True or payload.aplicar_default_a_existentes:
        CategoriaService.acquire_hierarchy_mutation_lock(session)
        token = payload.precondicion_preview
        if not token:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "CATALOG_PREVIEW_STALE",
                    "message": "Previsualiza el cambio antes de aplicarlo.",
                    "conteos": {},
                    "acciones_permitidas": ["previsualizar"],
                },
            )
        payload_data = payload.model_dump(
            mode="json",
            exclude_unset=True,
            exclude={"precondicion_preview"},
        )
        state, _, _, _ = category_attribute_service.required_attribute_impact(
            session, mapping
        )
        b3_preview_signer().verify(
            token,
            operation="UPDATE_CATEGORY_ATTRIBUTE",
            target=f"/api/v1/categorias/{item_id}/atributos/{mapping_id}",
            actor=str(usuario.id),
            payload=payload_data,
            state=state,
        )
    updated = category_attribute_service.update(
        session, mapping_id, payload, usuario_auditoria=str(usuario.id)
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Asignación no encontrada.")
    effective = get_effective_attributes(session, [item_id])
    result = next(
        (item for item in effective if str(item["mapping_id"]) == str(mapping_id)), None
    )
    if result is None:
        raise HTTPException(status_code=409, detail="La asignación no quedó efectiva.")
    return CategoriaAtributoEfectivoRead.model_validate(result)


@router.post(
    "/{item_id}/atributos/{mapping_id}/previsualizar",
    response_model=PreviewResponse,
    dependencies=[Depends(assign_category_attribute_permission)],
)
def previsualizar_configuracion_atributo_categoria(
    item_id: UUID = Path(...),
    mapping_id: UUID = Path(...),
    payload: CategoriaAtributoUpdate = Body(...),
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(assign_category_attribute_permission),
) -> PreviewResponse:
    mapping = session.get(CategoriaAtributo, mapping_id)
    if mapping is None or mapping.categoria_id != item_id or not mapping.activo:
        raise HTTPException(status_code=404, detail="Asignación no encontrada en la categoría.")
    state, affected_ids, missing_ids, product_names = (
        category_attribute_service.required_attribute_impact(session, mapping)
    )
    payload_data = payload.model_dump(
        mode="json",
        exclude_unset=True,
        exclude={"precondicion_preview"},
    )
    token = b3_preview_signer().issue(
        operation="UPDATE_CATEGORY_ATTRIBUTE",
        target=f"/api/v1/categorias/{item_id}/atributos/{mapping_id}",
        actor=str(usuario.id),
        payload=payload_data,
        state=state,
    )
    return PreviewResponse(
        operacion="UPDATE_CATEGORY_ATTRIBUTE",
        resumen=(
            f"{len(missing_ids)} de {len(affected_ids)} productos activos carecen de un valor válido."
            if missing_ids
            else f"No hay faltantes entre {len(affected_ids)} productos activos afectados."
        ),
        conteos={
            "productos_afectados": len(affected_ids),
            "productos_faltantes": len(missing_ids),
        },
        faltantes=[
            ImpactItem(
                id=product_id,
                nombre=product_names.get(product_id, "Producto"),
                motivo="No tiene un valor EAV activo válido para este atributo.",
            )
            for product_id in missing_ids
        ],
        conversiones=[],
        incompatibles=[],
        remapeos=[],
        cambio_unidad=None,
        requiere_confirmacion=(payload.obligatorio is True or payload.aplicar_default_a_existentes),
        acciones_permitidas=(
            ["aplicar_default", "proporcionar_valores", "cancelar"]
            if missing_ids
            else ["confirmar", "cancelar"]
        ),
        precondicion_preview=token,
    )


@router.post(
    "/{item_id}/atributos/{mapping_id}/previsualizar-remocion",
    response_model=PreviewResponse,
    dependencies=[Depends(assign_category_attribute_permission)],
)
def previsualizar_retiro_atributo_categoria(
    item_id: UUID = Path(...),
    mapping_id: UUID = Path(...),
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(assign_category_attribute_permission),
) -> PreviewResponse:
    mapping = session.get(CategoriaAtributo, mapping_id)
    if mapping is None or mapping.categoria_id != item_id or not mapping.activo:
        raise HTTPException(status_code=404, detail="Asignación no encontrada en la categoría.")
    state, affected, removed_values, missing, names, retained_values, pending_remaps = (
        category_attribute_service.local_removal_impact(session, mapping)
    )
    payload = {"confirmar": True}
    token = b3_preview_signer().issue(
        operation="REMOVE_CATEGORY_ATTRIBUTE",
        target=f"/api/v1/categorias/{item_id}/atributos/{mapping_id}",
        actor=str(usuario.id),
        payload=payload,
        state=state,
    )
    return PreviewResponse(
        operacion="REMOVE_CATEGORY_ATTRIBUTE",
        resumen=(
            f"Se quitará de esta categoría; se conservarán {len(retained_values)} valores aún aplicables y "
            f"se desactivarán {len(removed_values)} valores que dejarán de aplicar."
        ),
        conteos={
            "productos_afectados": len(affected),
            "valores_conservados": len(retained_values),
            "valores_desactivados": len(removed_values),
            "productos_faltantes": len(missing),
        },
        faltantes=[
            ImpactItem(
                id=product_id,
                nombre=names.get(product_id, "Producto"),
                motivo="La configuración efectiva resultante deja un atributo obligatorio sin valor válido.",
            )
            for product_id in missing
        ],
        conversiones=[],
        incompatibles=[],
        remapeos=[
            ImpactItem(
                id=remap.id,
                nombre=names.get(remap.producto_id, "Producto"),
                motivo=remap.motivo,
            )
            for remap in pending_remaps
        ],
        cambio_unidad=None,
        requiere_confirmacion=True,
        acciones_permitidas=(
            ["completar_valores", "cancelar"] if missing else ["confirmar", "cancelar"]
        ),
        precondicion_preview=token,
    )


@router.delete(
    "/{item_id}/atributos/{mapping_id}",
    dependencies=[Depends(assign_category_attribute_permission)],
)
def quitar_atributo_categoria(
    item_id: UUID = Path(...),
    mapping_id: UUID = Path(...),
    payload: CategoriaAtributoRemoveConfirmation = Body(...),
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(assign_category_attribute_permission),
) -> dict[str, Any]:
    CategoriaService.acquire_hierarchy_mutation_lock(session)
    mapping = session.get(CategoriaAtributo, mapping_id)
    if mapping is None or mapping.categoria_id != item_id or not mapping.activo:
        raise HTTPException(status_code=404, detail="Asignación no encontrada en la categoría.")
    state, _, _, missing, names, _, pending_remaps = (
        category_attribute_service.local_removal_impact(session, mapping)
    )
    b3_preview_signer().verify(
        payload.precondicion_preview,
        operation="REMOVE_CATEGORY_ATTRIBUTE",
        target=f"/api/v1/categorias/{item_id}/atributos/{mapping_id}",
        actor=str(usuario.id),
        payload={"confirmar": payload.confirmar},
        state=state,
    )
    if pending_remaps:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ATTRIBUTE_HAS_PENDING_REMAPS",
                "message": "Resuelve los remapeos antes de quitar esta asignación.",
                "conteos": {"remapeos_pendientes": len(pending_remaps)},
                "affected_ids": [str(remap.id) for remap in pending_remaps],
                "acciones_permitidas": ["resolver_remapeos", "cancelar"],
            },
        )
    category_attribute_service._raise_required_attribute_missing(missing, names)
    removed_value_ids = category_attribute_service.remove_local_assignment(
        session,
        mapping,
        usuario_auditoria=str(usuario.id),
    )
    return {"mapping_id": str(mapping_id), "valores_desactivados": len(removed_value_ids)}


@router.post(
    "/previsualizar",
    response_model=PreviewResponse,
    dependencies=[Depends(create_category_permission)],
)
def previsualizar_creacion_categoria_b3(
    payload: CategoriaCreate = Body(...),
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(create_category_permission),
) -> PreviewResponse:
    normalized = payload.model_dump(mode="json", exclude_unset=True)
    return _b3_preview_response(
        session,
        operation="CREATE_CATEGORY_B3",
        target=f"/api/v1/categorias:parent:{payload.parent_id}",
        actor_id=usuario.id,
        payload=normalized,
        parent_id=payload.parent_id,
    )


@router.post(
    "/{item_id}/reactivar",
    response_model=CategoriaRead,
    dependencies=[Depends(reactivate_category_permission)],
)
def reactivar_categoria(
    item_id: UUID = Path(...),
    session: Session = Depends(get_session),
) -> CategoriaRead:
    category = service.reactivate(session, item_id)
    if category is None:
        raise HTTPException(status_code=404, detail=f"Categoría {item_id} not found")
    return CategoriaRead.model_validate(category)


@router.get("/sin-clasificar/conteo")
def contar_sin_recategorizar(session: Session = Depends(get_session)) -> dict[str, int]:
    return {"count": service.contar_productos_sin_recategorizar(session)}


@router.get("/sin-clasificar/productos")
def listar_sin_recategorizar(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return service.listar_productos_sin_recategorizar(session)


@router.post("/recategorizar", dependencies=[Depends(require_roles("admin", "supervisor"))])
def recategorizar_productos(
    payload: RecategorizarProductosRequest,
    session: Session = Depends(get_session),
) -> dict[str, int]:
    return service.recategorizar_productos(session, payload.assignments)


@router.get(
    "/{item_id}",
    response_model=CategoriaRead,
    dependencies=[Depends(read_categories_permission)],
)
def get_categoria(
    item_id: UUID = Path(...),
    session: Session = Depends(get_session),
) -> CategoriaRead:
    obj = service.get(session, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"Categoría {item_id} not found")
    return CategoriaRead.model_validate(obj)


@router.post("", response_model=CategoriaRead, status_code=status.HTTP_201_CREATED)
def create_categoria(
    payload: CategoriaCreate | CategoriaB3CreateConfirmation = Body(...),
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(create_category_permission),
) -> CategoriaRead:
    if isinstance(payload, CategoriaB3CreateConfirmation):
        create_payload = payload.payload
        normalized = create_payload.model_dump(mode="json", exclude_unset=True)
        data = create_payload.model_dump(exclude_unset=True)
        _verify_b3_confirmation(
            session,
            operation="CREATE_CATEGORY_B3",
            target=f"/api/v1/categorias:parent:{create_payload.parent_id}",
            actor_id=usuario.id,
            payload=normalized,
            token=payload.precondicion_preview,
            parent_id=create_payload.parent_id,
        )
        created = service.create(session, data, confirmar_b3=True)
    else:
        created = service.create(
            session, payload.model_dump(exclude_unset=True)
        )
    return CategoriaRead.model_validate(created)


@router.post(
    "/{item_id}/previsualizar",
    response_model=PreviewResponse,
    dependencies=[Depends(update_category_permission)],
)
def previsualizar_movimiento_categoria_b3(
    item_id: UUID = Path(...),
    payload: CategoriaUpdate = Body(...),
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(update_category_permission),
) -> PreviewResponse:
    category = service.get(session, item_id)
    if category is None:
        raise HTTPException(status_code=404, detail=f"Categoría {item_id} not found")
    normalized = payload.model_dump(mode="json", exclude_unset=True)
    new_parent_id = payload.parent_id if "parent_id" in payload.model_fields_set else category.parent_id
    return _b3_preview_response(
        session,
        operation="MOVE_CATEGORY_B3",
        target=f"/api/v1/categorias/{item_id}:parent:{new_parent_id}",
        actor_id=usuario.id,
        payload=normalized,
        parent_id=new_parent_id,
        category_id=item_id,
    )


@router.put("/{item_id}", response_model=CategoriaRead)
def update_categoria(
    item_id: UUID = Path(...),
    payload: CategoriaUpdate | CategoriaB3UpdateConfirmation = Body(...),
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(update_category_permission),
) -> CategoriaRead:
    if isinstance(payload, CategoriaB3UpdateConfirmation):
        update_payload = payload.payload
        normalized = update_payload.model_dump(mode="json", exclude_unset=True)
        data = update_payload.model_dump(exclude_unset=True)
        category = service.get(session, item_id)
        if category is None:
            raise HTTPException(status_code=404, detail=f"Categoría {item_id} not found")
        new_parent_id = data.get("parent_id", category.parent_id)
        _verify_b3_confirmation(
            session,
            operation="MOVE_CATEGORY_B3",
            target=f"/api/v1/categorias/{item_id}:parent:{new_parent_id}",
            actor_id=usuario.id,
            payload=normalized,
            token=payload.precondicion_preview,
            parent_id=new_parent_id,
            category_id=item_id,
        )
        updated = service.update(session, item_id, data, confirmar_b3=True)
    else:
        updated = service.update(
            session, item_id, payload.model_dump(exclude_unset=True)
        )
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Categoría {item_id} not found")
    return CategoriaRead.model_validate(updated)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(deactivate_category_permission)])
def delete_categoria(
    item_id: UUID = Path(...),
    confirmar_baja_productos: bool = Query(False),
    session: Session = Depends(get_session),
) -> None:
    ok = service.delete(session, item_id, confirmar_baja_productos=confirmar_baja_productos)
    if ok is None:
        raise HTTPException(status_code=404, detail=f"Categoría {item_id} not found")
