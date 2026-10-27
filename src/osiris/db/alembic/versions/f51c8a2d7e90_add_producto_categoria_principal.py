"""Add nullable primary category to Product.

Revision ID: f51c8a2d7e90
Revises: f04b7c2a9e61
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f51c8a2d7e90"
down_revision: Union[str, None] = "f04b7c2a9e61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "ix_tbl_producto_categoria_principal_id"
FOREIGN_KEY_NAME = "fk_tbl_producto_categoria_principal"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "categoria_principal_id" in {
        column["name"] for column in inspector.get_columns("tbl_producto")
    }:
        raise RuntimeError("tbl_producto.categoria_principal_id already exists.")

    with op.batch_alter_table("tbl_producto") as batch:
        batch.add_column(sa.Column("categoria_principal_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            FOREIGN_KEY_NAME,
            "tbl_categoria",
            ["categoria_principal_id"],
            ["id"],
        )
    op.create_index(INDEX_NAME, "tbl_producto", ["categoria_principal_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if "categoria_principal_id" not in {
        column["name"] for column in sa.inspect(bind).get_columns("tbl_producto")
    }:
        return

    populated = bind.execute(
        sa.text(
            "SELECT count(*) FROM tbl_producto "
            "WHERE categoria_principal_id IS NOT NULL"
        )
    ).scalar_one()
    if populated:
        raise RuntimeError(
            "Cannot remove tbl_producto.categoria_principal_id while it contains "
            f"{populated} values. Reconcile/rollback Product writes first."
        )

    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("tbl_producto")}
    if INDEX_NAME in indexes:
        op.drop_index(INDEX_NAME, table_name="tbl_producto")
    with op.batch_alter_table("tbl_producto") as batch:
        batch.drop_column("categoria_principal_id")
