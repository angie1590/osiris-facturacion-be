"""Add auditable pending attribute value remaps.

Revision ID: d6f9a3c18b50
Revises: c5e8b2a64d31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "d6f9a3c18b50"
down_revision = "c5e8b2a64d31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tbl_producto_atributo_remapeo",
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False),
        sa.Column("usuario_auditoria", sa.String(length=255), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("producto_id", sa.Uuid(), nullable=False),
        sa.Column("atributo_id", sa.Uuid(), nullable=False),
        sa.Column("tipo_anterior", sa.String(length=20), nullable=False),
        sa.Column("tipo_nuevo", sa.String(length=20), nullable=False),
        sa.Column("valor_anterior", sa.JSON(), nullable=False),
        sa.Column("motivo", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["atributo_id"], ["tbl_atributo.id"]),
        sa.ForeignKeyConstraint(["producto_id"], ["tbl_producto.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tbl_producto_atributo_remapeo_activo", "tbl_producto_atributo_remapeo", ["activo"])
    op.create_index("ix_tbl_producto_atributo_remapeo_producto_id", "tbl_producto_atributo_remapeo", ["producto_id"])
    op.create_index("ix_tbl_producto_atributo_remapeo_atributo_id", "tbl_producto_atributo_remapeo", ["atributo_id"])


def downgrade() -> None:
    bind = op.get_bind()
    pending = bind.execute(
        sa.text("SELECT id FROM tbl_producto_atributo_remapeo WHERE activo = true LIMIT 1")
    ).first()
    if pending:
        raise RuntimeError("Cannot downgrade while pending product attribute remaps would be lost.")
    op.drop_index("ix_tbl_producto_atributo_remapeo_atributo_id", table_name="tbl_producto_atributo_remapeo")
    op.drop_index("ix_tbl_producto_atributo_remapeo_producto_id", table_name="tbl_producto_atributo_remapeo")
    op.drop_index("ix_tbl_producto_atributo_remapeo_activo", table_name="tbl_producto_atributo_remapeo")
    op.drop_table("tbl_producto_atributo_remapeo")