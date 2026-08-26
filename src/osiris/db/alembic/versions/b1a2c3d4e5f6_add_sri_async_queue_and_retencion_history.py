"""add sri async queue and retencion history

Revision ID: b1a2c3d4e5f6
Revises: e7c3d1a2b4f6
Create Date: 2026-02-20 13:05:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "b1a2c3d4e5f6"
down_revision = "e7c3d1a2b4f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tbl_retencion",
        sa.Column("estado_sri", sa.String(length=20), nullable=False, server_default=sa.text("'PENDIENTE'")),
    )
    op.add_column(
        "tbl_retencion",
        sa.Column("sri_intentos", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column("tbl_retencion", sa.Column("sri_ultimo_error", sa.String(length=1000), nullable=True))
    op.alter_column("tbl_retencion", "estado_sri", server_default=None)
    op.alter_column("tbl_retencion", "sri_intentos", server_default=None)

    op.create_table(
        "tbl_retencion_estado_historial",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entidad_id", sa.Uuid(), nullable=False),
        sa.Column("estado_anterior", sa.String(length=30), nullable=False),
        sa.Column("estado_nuevo", sa.String(length=30), nullable=False),
        sa.Column("motivo_cambio", sa.Text(), nullable=False),
        sa.Column("usuario_id", sa.String(length=255), nullable=True),
        sa.Column("fecha", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["entidad_id"], ["tbl_retencion.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tbl_retencion_estado_historial_id"),
        "tbl_retencion_estado_historial",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_retencion_estado_historial_entidad_id"),
        "tbl_retencion_estado_historial",
        ["entidad_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_retencion_estado_historial_usuario_id"),
        "tbl_retencion_estado_historial",
        ["usuario_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_retencion_estado_historial_fecha"),
        "tbl_retencion_estado_historial",
        ["fecha"],
        unique=False,
    )

    op.create_table(
        "tbl_documento_sri_cola",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("usuario_auditoria", sa.String(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("entidad_id", sa.Uuid(), nullable=False),
        sa.Column("tipo_documento", sa.String(length=30), nullable=False),
        sa.Column("estado", sa.String(length=30), nullable=False, server_default=sa.text("'PENDIENTE'")),
        sa.Column("intentos_realizados", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_intentos", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("proximo_intento_en", sa.DateTime(), nullable=True),
        sa.Column("ultimo_error", sa.String(length=1000), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tbl_documento_sri_cola_id"), "tbl_documento_sri_cola", ["id"], unique=False)
    op.create_index(
        op.f("ix_tbl_documento_sri_cola_activo"),
        "tbl_documento_sri_cola",
        ["activo"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_documento_sri_cola_created_by"),
        "tbl_documento_sri_cola",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_documento_sri_cola_updated_by"),
        "tbl_documento_sri_cola",
        ["updated_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_documento_sri_cola_entidad_id"),
        "tbl_documento_sri_cola",
        ["entidad_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_documento_sri_cola_tipo_documento"),
        "tbl_documento_sri_cola",
        ["tipo_documento"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_documento_sri_cola_proximo_intento_en"),
        "tbl_documento_sri_cola",
        ["proximo_intento_en"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_tbl_documento_sri_cola_proximo_intento_en"), table_name="tbl_documento_sri_cola")
    op.drop_index(op.f("ix_tbl_documento_sri_cola_tipo_documento"), table_name="tbl_documento_sri_cola")
    op.drop_index(op.f("ix_tbl_documento_sri_cola_entidad_id"), table_name="tbl_documento_sri_cola")
    op.drop_index(op.f("ix_tbl_documento_sri_cola_updated_by"), table_name="tbl_documento_sri_cola")
    op.drop_index(op.f("ix_tbl_documento_sri_cola_created_by"), table_name="tbl_documento_sri_cola")
    op.drop_index(op.f("ix_tbl_documento_sri_cola_activo"), table_name="tbl_documento_sri_cola")
    op.drop_index(op.f("ix_tbl_documento_sri_cola_id"), table_name="tbl_documento_sri_cola")
    op.drop_table("tbl_documento_sri_cola")

    op.drop_index(op.f("ix_tbl_retencion_estado_historial_fecha"), table_name="tbl_retencion_estado_historial")
    op.drop_index(op.f("ix_tbl_retencion_estado_historial_usuario_id"), table_name="tbl_retencion_estado_historial")
    op.drop_index(op.f("ix_tbl_retencion_estado_historial_entidad_id"), table_name="tbl_retencion_estado_historial")
    op.drop_index(op.f("ix_tbl_retencion_estado_historial_id"), table_name="tbl_retencion_estado_historial")
    op.drop_table("tbl_retencion_estado_historial")

    op.drop_column("tbl_retencion", "sri_ultimo_error")
    op.drop_column("tbl_retencion", "sri_intentos")
    op.drop_column("tbl_retencion", "estado_sri")
