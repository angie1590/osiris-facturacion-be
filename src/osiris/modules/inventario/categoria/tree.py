from __future__ import annotations

from typing import Any, cast as typing_cast
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, col, select

from osiris.domain.catalog_contracts import CategoryTreeNode
from osiris.modules.inventario.atributo.entity import Atributo
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria.resolver import get_effective_attribute_counts
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo


def _attribute_counts(
    session: Session, category_ids: list[UUID]
) -> tuple[dict[UUID, int], dict[UUID, int]]:
    own_rows = session.exec(
        select(
            col(CategoriaAtributo.categoria_id),
            func.count(func.distinct(col(Atributo.id))),
        )
        .join(Atributo, col(Atributo.id) == col(CategoriaAtributo.atributo_id))
        .where(
            col(CategoriaAtributo.activo).is_(True),
            col(Atributo.activo).is_(True),
        )
        .group_by(col(CategoriaAtributo.categoria_id))
    ).all()
    own_counts = {category_id: int(count) for category_id, count in own_rows}

    effective_counts = get_effective_attribute_counts(session, category_ids)
    return own_counts, effective_counts


def _category_nodes(session: Session) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    categories = session.exec(
        select(Categoria)
        .where(col(Categoria.activo).is_(True))
        .order_by(func.lower(func.trim(col(Categoria.nombre))), col(Categoria.id))
    ).all()
    by_id = {category.id: category for category in categories}
    for category in categories:
        if category.parent_id is not None and category.parent_id not in by_id:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "CATEGORY_PARENT_INACTIVE",
                    "message": "La jerarquia contiene una categoria con padre inexistente o inactivo.",
                    "conteos": {},
                    "acciones_permitidas": [],
                },
            )

    own_counts, effective_counts = _attribute_counts(
        session, [category.id for category in categories]
    )
    children_by_parent: dict[UUID | None, list[dict[str, Any]]] = {}
    node_by_id: dict[UUID, dict[str, Any]] = {}
    for category in categories:
        node = {
            "id": category.id,
            "nombre": category.nombre,
            "parent_id": category.parent_id,
            "tiene_hijos": False,
            "is_default": category.is_default,
            "atributos_propios_count": own_counts.get(category.id, 0),
            "atributos_efectivos_count": effective_counts.get(category.id, 0),
            "hijos": [],
        }
        node_by_id[category.id] = node
        children_by_parent.setdefault(category.parent_id, []).append(node)

    for category in categories:
        if category.parent_id is not None:
            parent_node = node_by_id[category.parent_id]
            parent_node["tiene_hijos"] = True
            parent_node["hijos"].append(node_by_id[category.id])

    roots = children_by_parent.get(None, [])
    seen: set[UUID] = set()
    stack: list[dict[str, Any]] = list(roots)
    while stack:
        node = stack.pop()
        category_id = typing_cast(UUID, node["id"])
        if category_id in seen:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "CATEGORY_CYCLE",
                    "message": "La jerarquia contiene un ciclo y no se puede mostrar.",
                    "conteos": {},
                    "acciones_permitidas": [],
                },
            )
        seen.add(category_id)
        stack.extend(typing_cast(list[dict[str, Any]], node["hijos"]))
    if len(seen) != len(categories):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "CATEGORY_CYCLE",
                "message": "La jerarquia contiene un ciclo y no se puede mostrar.",
                "conteos": {},
                "acciones_permitidas": [],
            },
        )
    selectable = [
        {
            "id": category.id,
            "nombre": category.nombre,
            "parent_id": category.parent_id,
            "tiene_hijos": False,
            "is_default": False,
            "atributos_propios_count": own_counts.get(category.id, 0),
            "atributos_efectivos_count": effective_counts.get(category.id, 0),
            "activo": True,
        }
        for category in categories
        if not node_by_id[category.id]["tiene_hijos"] and not category.is_default
    ]
    return roots, selectable


def get_category_tree(session: Session) -> list[CategoryTreeNode]:
    roots, _ = _category_nodes(session)
    return [CategoryTreeNode.model_validate(node) for node in roots]


def get_selectable_categories(session: Session) -> list[dict[str, Any]]:
    _, categories = _category_nodes(session)
    return categories