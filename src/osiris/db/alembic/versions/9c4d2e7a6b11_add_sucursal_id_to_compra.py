"""add sucursal_id to compra

Revision ID: 9c4d2e7a6b11
Revises: 5481adce2db3
Create Date: 2026-02-22 12:05:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "9c4d2e7a6b11"
down_revision: Union[str, None] = "5481adce2db3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _has_index(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    if not _has_column("tbl_compra", "sucursal_id"):
        op.add_column("tbl_compra", sa.Column("sucursal_id", sa.Uuid(), nullable=True))

    if not _has_index("tbl_compra", "ix_tbl_compra_sucursal_id"):
        op.create_index("ix_tbl_compra_sucursal_id", "tbl_compra", ["sucursal_id"], unique=False)


def downgrade() -> None:
    if _has_index("tbl_compra", "ix_tbl_compra_sucursal_id"):
        op.drop_index("ix_tbl_compra_sucursal_id", table_name="tbl_compra")

    if _has_column("tbl_compra", "sucursal_id"):
        op.drop_column("tbl_compra", "sucursal_id")

