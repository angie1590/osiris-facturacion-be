"""Limit the legacy product-category bridge to one row per product.

Revision ID: e1f4a8d63c20
Revises: d3b9e8a1c6f4
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f4a8d63c20"
down_revision: Union[str, None] = "d3b9e8a1c6f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE_NAME = "tbl_producto_categoria"
INDEX_NAME = "uq_tbl_producto_categoria_producto"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE_NAME not in inspector.get_table_names():
        raise RuntimeError("Cannot enforce one category per product: bridge table is missing.")

    columns = {column["name"] for column in inspector.get_columns(TABLE_NAME)}
    if "producto_id" not in columns:
        raise RuntimeError("Cannot enforce one category per product: producto_id is missing.")

    duplicate = bind.execute(
        sa.text(
            f"SELECT producto_id, count(*) AS relation_count FROM {TABLE_NAME} "
            "GROUP BY producto_id HAVING count(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate is not None:
        raise RuntimeError(
            "Cannot enforce one category per product: resolve duplicate bridge rows "
            f"for producto_id={duplicate.producto_id} (count={duplicate.relation_count})."
        )

    op.create_index(INDEX_NAME, TABLE_NAME, ["producto_id"], unique=True)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if any(index["name"] == INDEX_NAME for index in inspector.get_indexes(TABLE_NAME)):
        op.drop_index(INDEX_NAME, table_name=TABLE_NAME)