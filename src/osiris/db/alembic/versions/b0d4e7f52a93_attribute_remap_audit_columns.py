"""Align product attribute remap audit columns with AuditMixin.

Revision ID: b0d4e7f52a93
Revises: a9c3d6e41f82
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "b0d4e7f52a93"
down_revision = "a9c3d6e41f82"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tbl_producto_atributo_remapeo",
        sa.Column("created_by", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "tbl_producto_atributo_remapeo",
        sa.Column("updated_by", sa.String(length=255), nullable=True),
    )
    remaps = sa.table(
        "tbl_producto_atributo_remapeo",
        sa.column("usuario_auditoria", sa.String(length=255)),
        sa.column("created_by", sa.String(length=255)),
        sa.column("updated_by", sa.String(length=255)),
    )
    op.get_bind().execute(
        remaps.update().values(
            created_by=remaps.c.usuario_auditoria,
            updated_by=remaps.c.usuario_auditoria,
        )
    )
    for column_name in ("created_by", "updated_by"):
        op.create_index(
            f"ix_tbl_producto_atributo_remapeo_{column_name}",
            "tbl_producto_atributo_remapeo",
            [column_name],
        )


def downgrade() -> None:
    for column_name in ("updated_by", "created_by"):
        op.drop_index(
            f"ix_tbl_producto_atributo_remapeo_{column_name}",
            table_name="tbl_producto_atributo_remapeo",
        )
    with op.batch_alter_table("tbl_producto_atributo_remapeo") as batch_op:
        batch_op.drop_column("updated_by")
        batch_op.drop_column("created_by")