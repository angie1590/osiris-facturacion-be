from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import String, case, cast, func, literal
from sqlalchemy.orm import aliased
from sqlmodel import Session, col, select

from osiris.modules.inventario.atributo.entity import Atributo
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.common.unidad.entity import Unidad


def _select(*entities: Any) -> Any:
    return select(*entities)


def _ranked_effective_attributes(
    categoria_ids: list[UUID],
    *,
    por_categoria: bool,
    excluded_mapping_ids: set[UUID] | None = None,
) -> Any:
    paths = (
        _select(
            col(Categoria.id).label("categoria_objetivo_id"),
            col(Categoria.id).label("categoria_origen_id"),
            col(Categoria.parent_id).label("parent_id"),
            literal(0).label("profundidad"),
            (literal("|") + cast(col(Categoria.id), String) + literal("|")).label(
                "path"
            ),
        )
        .where(
            col(Categoria.id).in_(categoria_ids),
            col(Categoria.activo).is_(True),
        )
        .cte(name="categoria_ancestros_efectivos", recursive=True)
    )
    parent = aliased(Categoria, name="categoria_ancestro_padre")
    origin = aliased(Categoria, name="categoria_efectiva_origen")
    paths = paths.union_all(
        _select(
            paths.c.categoria_objetivo_id,
            col(parent.id),
            col(parent.parent_id),
            (paths.c.profundidad + 1).label("profundidad"),
            (paths.c.path + cast(col(parent.id), String) + literal("|")).label(
                "path"
            ),
        )
        .join(parent, col(parent.id) == paths.c.parent_id)
        .where(
            col(parent.activo).is_(True),
            paths.c.path.not_like(
                literal("%|") + cast(col(parent.id), String) + literal("|%")
            ),
        )
    )

    partition_by = [col(CategoriaAtributo.atributo_id)]
    if por_categoria:
        partition_by.insert(0, paths.c.categoria_objetivo_id)
    mapping_filters = [
        col(CategoriaAtributo.activo).is_(True),
        col(Atributo.activo).is_(True),
    ]
    if excluded_mapping_ids:
        mapping_filters.append(
            col(CategoriaAtributo.id).not_in(excluded_mapping_ids)
        )
    return (
        _select(
            paths.c.categoria_objetivo_id,
            paths.c.categoria_origen_id,
            paths.c.profundidad,
            col(origin.nombre).label("categoria_origen_nombre"),
            col(CategoriaAtributo.id).label("mapping_id"),
            col(CategoriaAtributo.atributo_id).label("atributo_id"),
            col(Atributo.codigo).label("codigo"),
            col(Atributo.nombre).label("atributo_nombre"),
            col(Atributo.tipo_dato).label("tipo_dato"),
            col(Atributo.select_options).label("select_options"),
            col(Atributo.catalog_id).label("catalog_id"),
            col(Atributo.allow_negative).label("allow_negative"),
            col(Atributo.min_value).label("min_value"),
            col(Atributo.max_value).label("max_value"),
            col(Atributo.unidad_id).label("unidad_id"),
            col(Unidad.codigo).label("unidad_codigo"),
            col(Unidad.nombre).label("unidad_nombre"),
            col(Unidad.simbolo).label("unidad_simbolo"),
            col(Unidad.magnitud_codigo).label("unidad_magnitud_codigo"),
            col(CategoriaAtributo.orden).label("orden"),
            col(CategoriaAtributo.obligatorio).label("obligatorio"),
            col(CategoriaAtributo.valor_default).label("valor_default"),
            func.row_number()
            .over(
                partition_by=partition_by,
                order_by=(
                    paths.c.profundidad.asc(),
                    paths.c.categoria_objetivo_id.asc(),
                    col(CategoriaAtributo.id).asc(),
                ),
            )
            .label("rn"),
        )
        .join(
            CategoriaAtributo,
            col(CategoriaAtributo.categoria_id) == paths.c.categoria_origen_id,
        )
        .join(origin, col(origin.id) == paths.c.categoria_origen_id)
        .join(Atributo, col(Atributo.id) == col(CategoriaAtributo.atributo_id))
        .outerjoin(Unidad, col(Unidad.id) == col(Atributo.unidad_id))
        .where(*mapping_filters)
        .cte(name="atributos_efectivos_ranked")
    )


def get_effective_attributes_by_category(
    session: Session,
    categoria_ids: list[UUID],
    *,
    excluded_mapping_ids: set[UUID] | None = None,
) -> dict[UUID, list[dict[str, Any]]]:
    if not categoria_ids:
        return {}
    ranked = _ranked_effective_attributes(
        categoria_ids,
        por_categoria=True,
        excluded_mapping_ids=excluded_mapping_ids,
    )
    rows = session.execute(
        select(ranked)
        .where(ranked.c.rn == 1)
        .order_by(
            ranked.c.categoria_objetivo_id,
            case((ranked.c.orden.is_(None), 1), else_=0),
            ranked.c.orden.asc(),
            func.lower(func.trim(ranked.c.atributo_nombre)).asc(),
            ranked.c.atributo_id,
        )
    ).all()
    result: dict[UUID, list[dict[str, Any]]] = {}
    for row in rows:
        result.setdefault(row.categoria_objetivo_id, []).append(
            _effective_attribute_payload(row)
        )
    return result


def _effective_attribute_payload(row: Any) -> dict[str, Any]:
    return {
        "mapping_id": row.mapping_id,
        "atributo_id": row.atributo_id,
        "codigo": row.codigo,
        "nombre": row.atributo_nombre,
        "atributo_nombre": row.atributo_nombre,
        "tipo_dato": row.tipo_dato,
        "unidad": (
            {
                "id": row.unidad_id,
                "codigo": row.unidad_codigo,
                "nombre": row.unidad_nombre,
                "simbolo": row.unidad_simbolo,
                "magnitud_codigo": row.unidad_magnitud_codigo,
            }
            if row.unidad_id is not None
            else None
        ),
        "restricciones": {
            "allow_negative": row.allow_negative,
            "min_value": row.min_value,
            "max_value": row.max_value,
        },
        "select_options": row.select_options,
        "catalog_id": row.catalog_id,
        "unidad_id": row.unidad_id,
        "allow_negative": row.allow_negative,
        "min_value": row.min_value,
        "max_value": row.max_value,
        "orden": row.orden,
        "obligatorio": bool(row.obligatorio),
        "valor_default": row.valor_default,
        "categoria_origen_id": row.categoria_origen_id,
        "categoria_origen": {
            "id": row.categoria_origen_id,
            "nombre": row.categoria_origen_nombre,
        },
        "profundidad": row.profundidad,
        "heredado": row.profundidad > 0,
    }


def _active_category_ancestors(
    session: Session, categoria_ids: list[UUID]
) -> dict[UUID, set[UUID]]:
    if not categoria_ids:
        return {}
    paths = (
        _select(
            col(Categoria.id).label("target_id"),
            col(Categoria.id).label("ancestor_id"),
            col(Categoria.parent_id).label("parent_id"),
            literal(0).label("depth"),
            (literal("|") + cast(col(Categoria.id), String) + literal("|")).label(
                "path"
            ),
        )
        .where(
            col(Categoria.id).in_(categoria_ids),
            col(Categoria.activo).is_(True),
        )
        .cte(name="active_category_scope_paths", recursive=True)
    )
    parent = aliased(Categoria, name="legacy_category_scope_parent")
    paths = paths.union_all(
        _select(
            paths.c.target_id,
            col(parent.id),
            col(parent.parent_id),
            (paths.c.depth + 1).label("depth"),
            (paths.c.path + cast(col(parent.id), String) + literal("|")).label(
                "path"
            ),
        )
        .join(parent, col(parent.id) == paths.c.parent_id)
        .where(
            col(parent.activo).is_(True),
            paths.c.path.not_like(
                literal("%|") + cast(col(parent.id), String) + literal("|%")
            ),
        )
    )
    rows = session.exec(select(paths.c.target_id, paths.c.ancestor_id)).all()
    ancestors_by_target: dict[UUID, set[UUID]] = {}
    for target_id, ancestor_id in rows:
        ancestors_by_target.setdefault(target_id, set()).add(ancestor_id)
    return ancestors_by_target


def resolve_unambiguous_category_scope(
    session: Session, categoria_ids: list[UUID]
) -> UUID | None:
    requested_ids = list(dict.fromkeys(categoria_ids))
    if not requested_ids:
        return None
    if len(requested_ids) == 1:
        return requested_ids[0]
    ancestors_by_target = _active_category_ancestors(session, requested_ids)

    scope_candidates = [
        target_id
        for target_id in requested_ids
        if set(requested_ids).issubset(ancestors_by_target.get(target_id, set()))
    ]
    if len(scope_candidates) == 1:
        return scope_candidates[0]

    raise HTTPException(
        status_code=409,
        detail={
            "code": "CATEGORY_ATTRIBUTE_SCOPE_AMBIGUOUS",
            "message": "El producto tiene categorías de ramas distintas; no se combinará la herencia de atributos.",
            "affected_ids": [str(category_id) for category_id in requested_ids],
            "acciones_permitidas": ["revisar_categorias"],
            "conteos": {"categorias": len(requested_ids)},
        },
    )


def ambiguous_product_category_scopes(
    session: Session, product_category_rows: Sequence[tuple[UUID, UUID]]
) -> list[UUID]:
    categories_by_product: dict[UUID, set[UUID]] = {}
    for product_id, category_id in product_category_rows:
        categories_by_product.setdefault(product_id, set()).add(category_id)
    ancestors_by_target = _active_category_ancestors(
        session,
        list(
            {
                category_id
                for category_ids in categories_by_product.values()
                for category_id in category_ids
            }
        ),
    )
    return [
        product_id
        for product_id, category_ids in categories_by_product.items()
        if not any(
            category_ids.issubset(ancestors_by_target.get(target_id, set()))
            for target_id in category_ids
        )
    ]


def get_effective_attribute_counts(
    session: Session, categoria_ids: list[UUID]
) -> dict[UUID, int]:
    if not categoria_ids:
        return {}
    ranked = _ranked_effective_attributes(categoria_ids, por_categoria=True)
    rows = session.exec(
        select(ranked.c.categoria_objetivo_id, func.count())
        .where(ranked.c.rn == 1)
        .group_by(ranked.c.categoria_objetivo_id)
    ).all()
    return {categoria_id: int(count) for categoria_id, count in rows}


def get_effective_attributes(
    session: Session, categoria_ids: list[UUID]
) -> list[dict[str, Any]]:
    if not categoria_ids:
        return []
    ranked = _ranked_effective_attributes(categoria_ids, por_categoria=False)
    rows = session.execute(
        select(ranked)
        .where(ranked.c.rn == 1)
        .order_by(
            case((ranked.c.orden.is_(None), 1), else_=0),
            ranked.c.orden.asc(),
            func.lower(func.trim(ranked.c.atributo_nombre)).asc(),
            ranked.c.atributo_id,
        )
    ).all()
    return [
        {
            "mapping_id": row.mapping_id,
            "atributo_id": row.atributo_id,
            "codigo": row.codigo,
            "nombre": row.atributo_nombre,
            "atributo_nombre": row.atributo_nombre,
            "tipo_dato": row.tipo_dato,
            "unidad": (
                {
                    "id": row.unidad_id,
                    "codigo": row.unidad_codigo,
                    "nombre": row.unidad_nombre,
                    "simbolo": row.unidad_simbolo,
                    "magnitud_codigo": row.unidad_magnitud_codigo,
                }
                if row.unidad_id is not None
                else None
            ),
            "restricciones": {
                "allow_negative": row.allow_negative,
                "min_value": row.min_value,
                "max_value": row.max_value,
            },
            "select_options": row.select_options,
            "catalog_id": row.catalog_id,
            "allow_negative": row.allow_negative,
            "min_value": row.min_value,
            "max_value": row.max_value,
            "unidad_id": row.unidad_id,
            "orden": row.orden,
            "obligatorio": bool(row.obligatorio),
            "valor_default": row.valor_default,
            "categoria_origen_id": row.categoria_origen_id,
            "categoria_origen": {
                "id": row.categoria_origen_id,
                "nombre": row.categoria_origen_nombre,
            },
            "profundidad": row.profundidad,
            "heredado": row.profundidad > 0,
        }
        for row in rows
    ]


def get_own_attributes(session: Session, categoria_id: UUID) -> list[dict[str, Any]]:
    return [
        attribute
        for attribute in get_effective_attributes(session, [categoria_id])
        if attribute["profundidad"] == 0
    ]