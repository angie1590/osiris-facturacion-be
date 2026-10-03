"""Add an explicit marker for temporary default categories.

Revision ID: b84c1d6e2f90
Revises: a73f2c9d1e60
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "b84c1d6e2f90"
down_revision = "a73f2c9d1e60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tbl_categoria",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_tbl_categoria_is_default", "tbl_categoria", ["is_default"])

    bind = op.get_bind()
    categories = sa.table(
        "tbl_categoria",
        sa.column("id", sa.Uuid()),
        sa.column("nombre", sa.String()),
        sa.column("parent_id", sa.Uuid()),
        sa.column("es_padre", sa.Boolean()),
        sa.column("activo", sa.Boolean()),
    )
    product_categories = sa.table(
        "tbl_producto_categoria",
        sa.column("producto_id", sa.Uuid()),
        sa.column("categoria_id", sa.Uuid()),
    )
    direct_products = sa.select(product_categories.c.categoria_id).distinct()
    possible_legacy_buckets = bind.execute(
        sa.select(categories.c.id, categories.c.parent_id)
        .where(
            sa.func.lower(categories.c.nombre) == "general",
            categories.c.parent_id.is_not(None),
            categories.c.activo.is_(True),
            categories.c.id.in_(direct_products),
        )
    ).all()
    if possible_legacy_buckets:
        candidates = ", ".join(
            f"category={category_id} parent={parent_id}"
            for category_id, parent_id in possible_legacy_buckets
        )
        print(
            "Review possible legacy B3 categories named General before marking them is_default; "
            "the schema has no origin marker, so none were changed automatically: "
            f"{candidates}"
        )


def downgrade() -> None:
    op.drop_index("ix_tbl_categoria_is_default", table_name="tbl_categoria")
    op.drop_column("tbl_categoria", "is_default")