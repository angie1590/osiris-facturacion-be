from __future__ import annotations

from hashlib import sha256
from typing import Any
from uuid import UUID

from sqlmodel import Session, col, select

from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.core.settings import get_settings
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.producto.entity import Producto
from osiris.utils.catalog_preview import CatalogPreviewSigner


def b3_preview_state(
    session: Session, parent_id: UUID | None, *, category_id: UUID | None = None
) -> tuple[dict[str, Any], list[UUID]]:
    parent = None
    direct_product_ids: list[UUID] = []
    bucket_state = None
    has_active_children = False
    if parent_id is not None:
        parent = session.exec(
            select(Categoria)
            .where(col(Categoria.id) == parent_id)
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        ).first()
        has_active_children = session.exec(
            select(col(Categoria.id))
            .where(
                col(Categoria.parent_id) == parent_id,
                col(Categoria.activo).is_(True),
            )
            .limit(1)
        ).first() is not None
        direct_product_ids = sorted(
            session.exec(
                select(col(Producto.id))
                .where(col(Producto.categoria_principal_id) == parent_id)
                .order_by(col(Producto.id))
            ).all(),
            key=str,
        )
        bucket = session.exec(
            select(Categoria)
            .where(
                col(Categoria.parent_id) == parent_id,
                col(Categoria.is_default).is_(True),
            )
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        ).first()
        if bucket is not None:
            bucket_state = {"id": str(bucket.id), "activo": bucket.activo}
    moving_category = (
        session.exec(
            select(Categoria)
            .where(col(Categoria.id) == category_id)
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        ).first()
        if category_id is not None
        else None
    )
    state = {
        "parent": (
            {
                "id": str(parent.id),
                "activo": parent.activo,
                "is_default": parent.is_default,
            }
            if parent is not None
            else None
        ),
        "category": (
            {
                "id": str(moving_category.id),
                "nombre": moving_category.nombre,
                "parent_id": str(moving_category.parent_id) if moving_category.parent_id else None,
                "activo": moving_category.activo,
            }
            if moving_category is not None
            else None
        ),
        "has_active_children": has_active_children,
        "direct_product_ids": [str(product_id) for product_id in direct_product_ids],
        "bucket": bucket_state,
    }
    return state, direct_product_ids


def b3_preview_signer() -> CatalogPreviewSigner:
    secret = get_settings().SECRET_KEY.encode("utf-8")
    return CatalogPreviewSigner(sha256(secret).digest())
