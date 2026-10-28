from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from hashlib import sha256
from typing import Any, cast
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, col, select

from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.core.settings import get_settings
from osiris.modules.common.catalogo.entity import CatalogoValor
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.inventario.atributo.entity import TipoDato
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria.resolver import get_effective_attributes
from osiris.modules.inventario.producto.entity import (
    Producto,
    ProductoCategoria,
    ProductoImpuesto,
)
from osiris.modules.inventario.producto.models import (
    ProductoCambioCategoriaImpacto,
    ProductoCambioCategoriaPreviewInput,
    ProductoCambioCategoriaPreviewResponse,
)
from osiris.modules.inventario.producto.models_atributos import ProductoAtributoValor
from osiris.modules.inventario.producto.service import ProductoService
from osiris.modules.inventario.producto.service_atributos import ProductoAtributoValorService
from osiris.modules.sri.impuesto_catalogo.entity import ImpuestoCatalogo
from osiris.utils.catalog_preview import CatalogPreviewSigner


OPERATION = "CHANGE_PRODUCT_PRIMARY_CATEGORY"


def product_preview_signer() -> CatalogPreviewSigner:
    secret = get_settings().SECRET_KEY.encode("utf-8")
    return CatalogPreviewSigner(sha256(secret).digest())


def _json_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def product_category_preview_payload(
    category_id: UUID,
    attributes: list[Any] | None,
) -> dict[str, Any]:
    return {
        "categoria_principal_id": str(category_id),
        "atributos": [
            {
                "atributo_id": str(item.atributo_id),
                "valor": _json_value(item.valor),
            }
            for item in (attributes or [])
        ],
    }


def _category_chain_state(session: Session, category_id: UUID | None) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    visited: set[UUID] = set()
    current_id = category_id
    while current_id is not None and current_id not in visited:
        visited.add(current_id)
        category = session.exec(
            select(Categoria)
            .where(col(Categoria.id) == current_id)
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        ).first()
        if category is None:
            chain.append({"id": str(current_id), "missing": True})
            break
        chain.append(
            {
                "id": str(category.id),
                "parent_id": str(category.parent_id) if category.parent_id else None,
                "nombre": category.nombre,
                "activo": category.activo,
                "is_default": category.is_default,
                "has_active_children": session.exec(
                    select(Categoria.id)
                    .where(
                        col(Categoria.parent_id) == category.id,
                        col(Categoria.activo).is_(True),
                    )
                    .limit(1)
                ).first()
                is not None,
            }
        )
        current_id = category.parent_id
    if current_id in visited:
        chain.append({"id": str(current_id), "cycle": True})
    return chain


def _category_path(session: Session, category_id: UUID | None) -> str | None:
    chain = _category_chain_state(session, category_id)
    if category_id is None or any(item.get("missing") or item.get("cycle") for item in chain):
        return None
    return " > ".join(str(item["nombre"]) for item in reversed(chain))


def _effective_value_is_valid(
    session: Session,
    attribute: dict[str, Any],
    value: Any,
) -> bool:
    try:
        kind_value = attribute["tipo_dato"]
        kind = kind_value if isinstance(kind_value, TipoDato) else TipoDato(str(kind_value).lower())
        field_name, cast_value = ProductoAtributoValorService()._cast_by_tipo(kind, value)
        if kind == TipoDato.SELECT:
            options = attribute.get("select_options") or []
            if not any(str(option).casefold() == str(cast_value).casefold() for option in options):
                return False
        elif kind == TipoDato.CATALOG:
            catalog_id = attribute.get("catalog_id")
            if catalog_id is None:
                return False
            active_value = session.exec(
                select(CatalogoValor.id).where(
                    col(CatalogoValor.catalogo_id) == catalog_id,
                    col(CatalogoValor.activo).is_(True),
                    col(CatalogoValor.valor) == str(cast_value),
                )
            ).first()
            if active_value is None:
                return False
        elif kind in {TipoDato.INTEGER, TipoDato.DECIMAL}:
            numeric_value = Decimal(str(cast_value))
            if not numeric_value.is_finite():
                return False
            if not attribute.get("allow_negative", False) and numeric_value < 0:
                return False
            min_value = attribute.get("min_value")
            max_value = attribute.get("max_value")
            if min_value is not None and numeric_value < Decimal(str(min_value)):
                return False
            if max_value is not None and numeric_value > Decimal(str(max_value)):
                return False
        return bool(field_name)
    except (InvalidOperation, TypeError, ValueError, KeyError):
        return False


def _active_eav_state(session: Session, product_id: UUID) -> list[dict[str, Any]]:
    values = session.exec(
        select(ProductoAtributoValor)
        .where(col(ProductoAtributoValor.producto_id) == product_id)
        .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        .order_by(col(ProductoAtributoValor.id))
    ).all()
    return [
        {
            "id": value.id,
            "atributo_id": value.atributo_id,
            "activo": value.activo,
            "valor_string": value.valor_string,
            "valor_integer": value.valor_integer,
            "valor_decimal": value.valor_decimal,
            "valor_boolean": value.valor_boolean,
            "valor_date": value.valor_date,
            "actualizado_en": value.actualizado_en,
        }
        for value in values
    ]


def _active_tax_state(session: Session, product_id: UUID) -> list[dict[str, Any]]:
    taxes = session.exec(
        select(ProductoImpuesto)
        .where(col(ProductoImpuesto.producto_id) == product_id)
        .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        .order_by(col(ProductoImpuesto.id))
    ).all()
    state: list[dict[str, Any]] = []
    for tax in taxes:
        tax_definition = session.exec(
            select(ImpuestoCatalogo)
            .where(col(ImpuestoCatalogo.id) == tax.impuesto_catalogo_id)
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        ).first()
        company = session.get(Empresa, tax.empresa_id) if tax.empresa_id else None
        state.append(
            {
                "id": tax.id,
                "impuesto_catalogo_id": tax.impuesto_catalogo_id,
                "empresa_id": tax.empresa_id,
                "activo": tax.activo,
                "tax_definition": (
                    {
                        "activo": tax_definition.activo,
                        "vigente_desde": tax_definition.vigente_desde,
                        "vigente_hasta": tax_definition.vigente_hasta,
                        "aplica_a": tax_definition.aplica_a,
                        "codigo_sri": tax_definition.codigo_sri,
                        "porcentaje_iva": tax_definition.porcentaje_iva,
                        "tarifa_ad_valorem": tax_definition.tarifa_ad_valorem,
                    }
                    if tax_definition is not None
                    else None
                ),
                "company_tax_ids": company.impuesto_catalogo_ids if company else None,
            }
        )
    return state


def product_category_preview_state(
    session: Session,
    product: Producto,
    current_category_id: UUID | None,
    target_category_id: UUID,
    bridge_category_ids: list[UUID],
) -> dict[str, Any]:
    category_ids = sorted(
        {category_id for category_id in (current_category_id, target_category_id) if category_id},
        key=str,
    )
    effective = {
        category_id: get_effective_attributes(session, [category_id])
        for category_id in category_ids
    }
    return cast(dict[str, Any], _json_value(
        {
            "producto": {
                "id": product.id,
                "activo": product.activo,
                "actualizado_en": product.actualizado_en,
                "categoria_principal_id": product.categoria_principal_id,
            },
            "bridge_category_ids": bridge_category_ids,
            "category_chains": {
                str(category_id): _category_chain_state(session, category_id)
                for category_id in category_ids
            },
            "effective_attributes": effective,
            "eav": _active_eav_state(session, product.id),
            "taxes": _active_tax_state(session, product.id),
        }
    ))


def preview_product_category_change(
    session: Session,
    product_id: UUID,
    payload: ProductoCambioCategoriaPreviewInput,
    *,
    actor_id: UUID,
) -> ProductoCambioCategoriaPreviewResponse:
    product = session.exec(
        select(Producto).where(col(Producto.id) == product_id)
    ).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")

    bridge_category_ids = list(
        session.exec(
            select(ProductoCategoria.categoria_id)
            .where(col(ProductoCategoria.producto_id) == product_id)
            .order_by(col(ProductoCategoria.categoria_id))
        ).all()
    )
    current_category_id = product.categoria_principal_id
    if product.activo and current_category_id is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PRODUCT_CATEGORY_REQUIRED",
                "message": "El producto activo no tiene una categoría principal.",
            },
        )
    if len(bridge_category_ids) > 1 or (
        product.categoria_principal_id is not None
        and bridge_category_ids != [product.categoria_principal_id]
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PRODUCT_PRIMARY_CATEGORY_CONFLICT",
                "message": "La categoría principal y la proyección legacy no coinciden.",
            },
        )

    target = session.get(Categoria, payload.categoria_principal_id)
    if target is None or not target.activo:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "PRODUCT_CATEGORY_INVALID",
                "message": "La categoría destino no existe o está inactiva.",
            },
        )
    if target.is_default or session.exec(
        select(Categoria.id)
        .where(col(Categoria.parent_id) == target.id, col(Categoria.activo).is_(True))
        .limit(1)
    ).first() is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PRODUCT_CATEGORY_NOT_SELECTABLE",
                "message": "La categoría destino debe ser una hoja activa seleccionable.",
            },
        )

    old_attributes = (
        get_effective_attributes(session, [current_category_id])
        if current_category_id is not None
        else []
    )
    target_attributes = get_effective_attributes(session, [target.id])
    old_by_id = {attribute["atributo_id"]: attribute for attribute in old_attributes}
    target_by_id = {attribute["atributo_id"]: attribute for attribute in target_attributes}
    old_required_ids = {
        attribute_id
        for attribute_id, definition in old_by_id.items()
        if definition["obligatorio"] is True
    }
    new_required_ids = {
        attribute_id
        for attribute_id, definition in target_by_id.items()
        if definition["obligatorio"] is True and attribute_id not in old_required_ids
    }
    provided = {item.atributo_id: item.valor for item in payload.atributos}
    unknown = set(provided) - set(target_by_id) - set(old_by_id)
    if unknown:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "PRODUCT_ATTRIBUTE_NOT_APPLICABLE",
                "message": "Uno o más atributos no aplican a la categoría destino.",
                "fields": {
                    f"atributos.{attribute_id}": "El atributo no aplica a la categoría destino."
                    for attribute_id in sorted(unknown, key=str)
                },
            },
        )

    values = session.exec(
        select(ProductoAtributoValor)
        .where(
            col(ProductoAtributoValor.producto_id) == product_id,
            col(ProductoAtributoValor.activo).is_(True),
        )
        .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
    ).all()
    values_by_id: dict[UUID, list[ProductoAtributoValor]] = {}
    for value in values:
        values_by_id.setdefault(value.atributo_id, []).append(value)

    conserved: list[ProductoCambioCategoriaImpacto] = []
    deactivated: list[ProductoCambioCategoriaImpacto] = []
    defaults: list[ProductoCambioCategoriaImpacto] = []
    missing: list[ProductoCambioCategoriaImpacto] = []
    incompatible: list[ProductoCambioCategoriaImpacto] = []

    for attribute_id, records in values_by_id.items():
        old_definition = old_by_id.get(attribute_id)
        target_definition = target_by_id.get(attribute_id)
        attribute_name = str(
            (target_definition or old_definition or {}).get("atributo_nombre", "Atributo")
        )
        raw_value = (
            ProductoService._extract_valor_por_tipo(
                (old_definition or target_definition or {}).get("tipo_dato"), records[0]
            )
            if len(records) == 1
            else None
        )
        if target_definition is None:
            deactivated.append(
                ProductoCambioCategoriaImpacto(
                    atributo_id=attribute_id,
                    codigo=str((old_definition or {}).get("codigo", "")),
                    nombre=attribute_name,
                    valor=raw_value,
                    motivo="El atributo no aplica a la categoría destino.",
                )
            )
            continue
        if len(records) > 1:
            incompatible.append(
                ProductoCambioCategoriaImpacto(
                    atributo_id=attribute_id,
                    codigo=str(target_definition.get("codigo", "")),
                    nombre=attribute_name,
                    valor=None,
                    motivo="Hay varios valores EAV activos para el atributo.",
                )
            )
            continue
        if attribute_id in provided:
            proposed_value = provided[attribute_id]
            if proposed_value is None and target_definition["obligatorio"]:
                missing.append(
                    ProductoCambioCategoriaImpacto(
                        atributo_id=attribute_id,
                        codigo=str(target_definition.get("codigo", "")),
                        nombre=attribute_name,
                        motivo="El atributo obligatorio no puede limpiarse.",
                    )
                )
                continue
            if proposed_value is None:
                deactivated.append(
                    ProductoCambioCategoriaImpacto(
                        atributo_id=attribute_id,
                        codigo=str(target_definition.get("codigo", "")),
                        nombre=attribute_name,
                        valor=raw_value,
                        motivo="El borrador solicita limpiar el atributo opcional.",
                    )
                )
                continue
            raw_value = proposed_value
        if not _effective_value_is_valid(session, target_definition, raw_value):
            incompatible.append(
                ProductoCambioCategoriaImpacto(
                    atributo_id=attribute_id,
                    codigo=str(target_definition.get("codigo", "")),
                    nombre=attribute_name,
                    valor=raw_value,
                    motivo="El valor actual/propuesto no cumple el tipo o restricciones destino.",
                )
            )
            continue
        conserved.append(
            ProductoCambioCategoriaImpacto(
                atributo_id=attribute_id,
                codigo=str(target_definition.get("codigo", "")),
                nombre=attribute_name,
                valor=raw_value,
                motivo="El atributo sigue siendo efectivo y su valor es compatible.",
            )
        )

    for attribute_id, definition in target_by_id.items():
        if not definition["obligatorio"] or attribute_id in values_by_id:
            continue
        if attribute_id in provided:
            provided_value = provided[attribute_id]
            if provided_value is None:
                missing.append(
                    ProductoCambioCategoriaImpacto(
                        atributo_id=attribute_id,
                        codigo=str(definition.get("codigo", "")),
                        nombre=str(definition.get("atributo_nombre", "Atributo")),
                        motivo="El borrador limpia un atributo obligatorio.",
                    )
                )
                continue
            if _effective_value_is_valid(session, definition, value):
                continue
            incompatible.append(
                ProductoCambioCategoriaImpacto(
                    atributo_id=attribute_id,
                    codigo=str(definition.get("codigo", "")),
                    nombre=str(definition.get("atributo_nombre", "Atributo")),
                    valor=value,
                    motivo="El valor propuesto no cumple el tipo o restricciones destino.",
                )
            )
            continue
        default_value = definition.get("valor_default")
        if default_value is not None and _effective_value_is_valid(session, definition, default_value):
            defaults.append(
                ProductoCambioCategoriaImpacto(
                    atributo_id=attribute_id,
                    codigo=str(definition.get("codigo", "")),
                    nombre=str(definition.get("atributo_nombre", "Atributo")),
                    valor=default_value,
                    motivo="Se aplicará el default explícito de la categoría.",
                )
            )
        else:
            missing.append(
                ProductoCambioCategoriaImpacto(
                    atributo_id=attribute_id,
                    codigo=str(definition.get("codigo", "")),
                    nombre=str(definition.get("atributo_nombre", "Atributo")),
                    motivo="Atributo obligatorio sin valor ni default explícito válido.",
                )
            )

    for attribute_id, provided_value in provided.items():
        if attribute_id not in target_by_id:
            continue
        definition = target_by_id[attribute_id]
        if (
            definition["obligatorio"]
            or attribute_id in values_by_id
            or provided_value is None
        ):
            continue
        if not _effective_value_is_valid(session, definition, provided_value):
            incompatible.append(
                ProductoCambioCategoriaImpacto(
                    atributo_id=attribute_id,
                    codigo=str(definition.get("codigo", "")),
                    nombre=str(definition.get("atributo_nombre", "Atributo")),
                    valor=provided_value,
                    motivo="El valor propuesto no cumple el tipo o restricciones destino.",
                )
            )

    payload_data = product_category_preview_payload(
        payload.categoria_principal_id,
        payload.atributos,
    )
    state = product_category_preview_state(
        session,
        product,
        current_category_id,
        target.id,
        bridge_category_ids,
    )
    token = product_preview_signer().issue(
        operation=OPERATION,
        target=f"/api/v1/productos/{product_id}/previsualizar-cambio-categoria",
        actor=str(actor_id),
        payload=payload_data,
        state=state,
    )
    requires_confirmation = current_category_id != target.id
    counts = {
        "atributos_conservados": len(conserved),
        "valores_desactivados": len(deactivated),
        "defaults_disponibles": len(defaults),
        "nuevos_obligatorios": len(new_required_ids),
        "faltantes": len(missing),
        "incompatibles": len(incompatible),
    }
    summary = (
        f"{len(conserved)} valores se conservan, {len(deactivated)} dejan de aplicar, "
        f"{len(defaults)} defaults disponibles y {len(missing)} obligatorios faltantes."
    )
    actions = (
        ["proporcionar_valores", "confirmar", "cancelar"]
        if missing or incompatible
        else ["confirmar", "cancelar"]
    )
    return ProductoCambioCategoriaPreviewResponse(
        operacion=OPERATION,
        producto_id=product_id,
        categoria_actual_id=current_category_id,
        categoria_actual_ruta=_category_path(session, current_category_id),
        categoria_destino_id=target.id,
        categoria_destino_ruta=_category_path(session, target.id) or target.nombre,
        resumen=summary,
        conteos=counts,
        conservados=conserved,
        desactivados=deactivated,
        defaults=defaults,
        faltantes=missing,
        incompatibles=incompatible,
        requiere_confirmacion=requires_confirmation,
        acciones_permitidas=actions,
        precondicion_preview=token,
    )
