"""add retencion tables and cxp integration

Revision ID: e7c3d1a2b4f6
Revises: c6a1b2d3e4f5
Create Date: 2026-02-20 12:15:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "e7c3d1a2b4f6"
down_revision = "c6a1b2d3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tbl_retencion",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("usuario_auditoria", sa.String(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("compra_id", sa.Uuid(), nullable=False),
        sa.Column("fecha_emision", sa.Date(), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default=sa.text("'BORRADOR'")),
        sa.Column("total_retenido", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["compra_id"], ["tbl_compra.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("compra_id"),
    )
    op.create_index(op.f("ix_tbl_retencion_id"), "tbl_retencion", ["id"], unique=False)
    op.create_index(op.f("ix_tbl_retencion_activo"), "tbl_retencion", ["activo"], unique=False)
    op.create_index(op.f("ix_tbl_retencion_compra_id"), "tbl_retencion", ["compra_id"], unique=False)
    op.create_index(op.f("ix_tbl_retencion_fecha_emision"), "tbl_retencion", ["fecha_emision"], unique=False)
    op.create_index(op.f("ix_tbl_retencion_created_by"), "tbl_retencion", ["created_by"], unique=False)
    op.create_index(op.f("ix_tbl_retencion_updated_by"), "tbl_retencion", ["updated_by"], unique=False)

    op.create_table(
        "tbl_retencion_detalle",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("usuario_auditoria", sa.String(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("retencion_id", sa.Uuid(), nullable=False),
        sa.Column("codigo_retencion_sri", sa.String(length=10), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("porcentaje", sa.Numeric(7, 4), nullable=False),
        sa.Column("base_calculo", sa.Numeric(12, 2), nullable=False),
        sa.Column("valor_retenido", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["retencion_id"], ["tbl_retencion.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tbl_retencion_detalle_id"), "tbl_retencion_detalle", ["id"], unique=False)
    op.create_index(op.f("ix_tbl_retencion_detalle_activo"), "tbl_retencion_detalle", ["activo"], unique=False)
    op.create_index(op.f("ix_tbl_retencion_detalle_retencion_id"), "tbl_retencion_detalle", ["retencion_id"], unique=False)
    op.create_index(op.f("ix_tbl_retencion_detalle_created_by"), "tbl_retencion_detalle", ["created_by"], unique=False)
    op.create_index(op.f("ix_tbl_retencion_detalle_updated_by"), "tbl_retencion_detalle", ["updated_by"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tbl_retencion_detalle_updated_by"), table_name="tbl_retencion_detalle")
    op.drop_index(op.f("ix_tbl_retencion_detalle_created_by"), table_name="tbl_retencion_detalle")
    op.drop_index(op.f("ix_tbl_retencion_detalle_retencion_id"), table_name="tbl_retencion_detalle")
    op.drop_index(op.f("ix_tbl_retencion_detalle_activo"), table_name="tbl_retencion_detalle")
    op.drop_index(op.f("ix_tbl_retencion_detalle_id"), table_name="tbl_retencion_detalle")
    op.drop_table("tbl_retencion_detalle")

    op.drop_index(op.f("ix_tbl_retencion_updated_by"), table_name="tbl_retencion")
    op.drop_index(op.f("ix_tbl_retencion_created_by"), table_name="tbl_retencion")
    op.drop_index(op.f("ix_tbl_retencion_fecha_emision"), table_name="tbl_retencion")
    op.drop_index(op.f("ix_tbl_retencion_compra_id"), table_name="tbl_retencion")
    op.drop_index(op.f("ix_tbl_retencion_activo"), table_name="tbl_retencion")
    op.drop_index(op.f("ix_tbl_retencion_id"), table_name="tbl_retencion")
    op.drop_table("tbl_retencion")
