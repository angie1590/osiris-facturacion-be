"""add plantilla retencion tables

Revision ID: c6a1b2d3e4f5
Revises: b4d9e2f1a6c3
Create Date: 2026-02-20 11:40:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "c6a1b2d3e4f5"
down_revision = "b4d9e2f1a6c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tbl_plantilla_retencion",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("usuario_auditoria", sa.String(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("proveedor_id", sa.Uuid(), nullable=True),
        sa.Column("nombre", sa.String(length=150), nullable=False, server_default=sa.text("'Plantilla Retencion'")),
        sa.Column("es_global", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tbl_plantilla_retencion_id"), "tbl_plantilla_retencion", ["id"], unique=False)
    op.create_index(
        op.f("ix_tbl_plantilla_retencion_activo"),
        "tbl_plantilla_retencion",
        ["activo"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_plantilla_retencion_created_by"),
        "tbl_plantilla_retencion",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_plantilla_retencion_updated_by"),
        "tbl_plantilla_retencion",
        ["updated_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_plantilla_retencion_proveedor_id"),
        "tbl_plantilla_retencion",
        ["proveedor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_plantilla_retencion_es_global"),
        "tbl_plantilla_retencion",
        ["es_global"],
        unique=False,
    )

    op.create_table(
        "tbl_plantilla_retencion_detalle",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("usuario_auditoria", sa.String(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("plantilla_retencion_id", sa.Uuid(), nullable=False),
        sa.Column("codigo_retencion_sri", sa.String(length=10), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("porcentaje", sa.Numeric(7, 4), nullable=False),
        sa.ForeignKeyConstraint(["plantilla_retencion_id"], ["tbl_plantilla_retencion.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tbl_plantilla_retencion_detalle_id"),
        "tbl_plantilla_retencion_detalle",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_plantilla_retencion_detalle_activo"),
        "tbl_plantilla_retencion_detalle",
        ["activo"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_plantilla_retencion_detalle_created_by"),
        "tbl_plantilla_retencion_detalle",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_plantilla_retencion_detalle_updated_by"),
        "tbl_plantilla_retencion_detalle",
        ["updated_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_plantilla_retencion_detalle_plantilla_retencion_id"),
        "tbl_plantilla_retencion_detalle",
        ["plantilla_retencion_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_tbl_plantilla_retencion_detalle_plantilla_retencion_id"),
        table_name="tbl_plantilla_retencion_detalle",
    )
    op.drop_index(op.f("ix_tbl_plantilla_retencion_detalle_updated_by"), table_name="tbl_plantilla_retencion_detalle")
    op.drop_index(op.f("ix_tbl_plantilla_retencion_detalle_created_by"), table_name="tbl_plantilla_retencion_detalle")
    op.drop_index(op.f("ix_tbl_plantilla_retencion_detalle_activo"), table_name="tbl_plantilla_retencion_detalle")
    op.drop_index(op.f("ix_tbl_plantilla_retencion_detalle_id"), table_name="tbl_plantilla_retencion_detalle")
    op.drop_table("tbl_plantilla_retencion_detalle")

    op.drop_index(op.f("ix_tbl_plantilla_retencion_es_global"), table_name="tbl_plantilla_retencion")
    op.drop_index(op.f("ix_tbl_plantilla_retencion_proveedor_id"), table_name="tbl_plantilla_retencion")
    op.drop_index(op.f("ix_tbl_plantilla_retencion_updated_by"), table_name="tbl_plantilla_retencion")
    op.drop_index(op.f("ix_tbl_plantilla_retencion_created_by"), table_name="tbl_plantilla_retencion")
    op.drop_index(op.f("ix_tbl_plantilla_retencion_activo"), table_name="tbl_plantilla_retencion")
    op.drop_index(op.f("ix_tbl_plantilla_retencion_id"), table_name="tbl_plantilla_retencion")
    op.drop_table("tbl_plantilla_retencion")
