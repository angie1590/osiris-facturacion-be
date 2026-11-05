"""Drop the retired product-category bridge after FK postflight.

Revision ID: f6a2c9d1e740
Revises: e1f4a8d63c20
"""

from __future__ import annotations

from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "f6a2c9d1e740"
down_revision: Union[str, None] = "e1f4a8d63c20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE_NAME = "tbl_producto_categoria"
UNIQUE_INDEX_NAME = "uq_tbl_producto_categoria_producto"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if TABLE_NAME not in tables:
        raise RuntimeError("Cannot retire product-category bridge: table is missing.")
    if "tbl_producto" not in tables:
        raise RuntimeError("Cannot retire product-category bridge: product table is missing.")

    product_columns = {
        column["name"] for column in inspector.get_columns("tbl_producto")
    }
    bridge_columns = {
        column["name"] for column in inspector.get_columns(TABLE_NAME)
    }
    if "categoria_principal_id" not in product_columns:
        raise RuntimeError(
            "Cannot retire product-category bridge: categoria_principal_id is missing."
        )
    if not {"producto_id", "categoria_id"} <= bridge_columns:
        raise RuntimeError(
            "Cannot retire product-category bridge: required relation columns are missing."
        )

    divergence_count = bind.execute(
        sa.text(
            "SELECT count(*) FROM tbl_producto p "
            "LEFT JOIN tbl_producto_categoria c ON c.producto_id = p.id "
            "WHERE (p.categoria_principal_id IS NULL AND c.producto_id IS NOT NULL) "
            "OR (p.categoria_principal_id IS NOT NULL AND "
            "(c.producto_id IS NULL OR c.categoria_id IS DISTINCT FROM p.categoria_principal_id))"
        )
    ).scalar_one()
    if divergence_count:
        raise RuntimeError(
            "Cannot retire product-category bridge: "
            f"{divergence_count} products are missing a matching primary-category projection."
        )

    op.drop_table(TABLE_NAME)


def downgrade() -> None:
    bind = op.get_bind()
    if TABLE_NAME in sa.inspect(bind).get_table_names():
        return

    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("producto_id", sa.Uuid(), nullable=False),
        sa.Column("categoria_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["categoria_id"], ["tbl_categoria.id"]),
        sa.ForeignKeyConstraint(["producto_id"], ["tbl_producto.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tbl_producto_categoria_categoria_id",
        TABLE_NAME,
        ["categoria_id"],
        unique=False,
    )
    op.create_index("ix_tbl_producto_categoria_id", TABLE_NAME, ["id"], unique=False)
    op.create_index(
        "ix_tbl_producto_categoria_producto_id",
        TABLE_NAME,
        ["producto_id"],
        unique=False,
    )
    op.create_index(UNIQUE_INDEX_NAME, TABLE_NAME, ["producto_id"], unique=True)

    products = bind.execute(
        sa.text(
            "SELECT id, categoria_principal_id FROM tbl_producto "
            "WHERE categoria_principal_id IS NOT NULL"
        )
    ).all()
    if products:
        bind.execute(
            sa.text(
                "INSERT INTO tbl_producto_categoria (id, producto_id, categoria_id) "
                "VALUES (:id, :producto_id, :categoria_id)"
            ),
            [
                {
                    "id": str(uuid4()),
                    "producto_id": str(product_id),
                    "categoria_id": str(category_id),
                }
                for product_id, category_id in products
            ],
        )