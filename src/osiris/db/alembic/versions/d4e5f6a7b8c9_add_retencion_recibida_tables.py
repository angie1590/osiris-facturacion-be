"""add retencion recibida tables

Revision ID: d4e5f6a7b8c9
Revises: b1a2c3d4e5f6
Create Date: 2026-02-20 14:05:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "b1a2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tbl_retencion_recibida",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("usuario_auditoria", sa.String(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("venta_id", sa.Uuid(), nullable=False),
        sa.Column("cliente_id", sa.Uuid(), nullable=False),
        sa.Column("numero_retencion", sa.String(length=20), nullable=False),
        sa.Column("clave_acceso_sri", sa.String(length=49), nullable=True),
        sa.Column("fecha_emision", sa.Date(), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default=sa.text("'BORRADOR'")),
        sa.Column("total_retenido", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["venta_id"], ["tbl_venta.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cliente_id", "numero_retencion", name="uq_retencion_recibida_cliente_numero"),
    )
    op.create_index(op.f("ix_tbl_retencion_recibida_id"), "tbl_retencion_recibida", ["id"], unique=False)
    op.create_index(op.f("ix_tbl_retencion_recibida_activo"), "tbl_retencion_recibida", ["activo"], unique=False)
    op.create_index(op.f("ix_tbl_retencion_recibida_created_by"), "tbl_retencion_recibida", ["created_by"], unique=False)
    op.create_index(op.f("ix_tbl_retencion_recibida_updated_by"), "tbl_retencion_recibida", ["updated_by"], unique=False)
    op.create_index(op.f("ix_tbl_retencion_recibida_venta_id"), "tbl_retencion_recibida", ["venta_id"], unique=False)
    op.create_index(op.f("ix_tbl_retencion_recibida_cliente_id"), "tbl_retencion_recibida", ["cliente_id"], unique=False)
    op.create_index(
        op.f("ix_tbl_retencion_recibida_clave_acceso_sri"),
        "tbl_retencion_recibida",
        ["clave_acceso_sri"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_retencion_recibida_fecha_emision"),
        "tbl_retencion_recibida",
        ["fecha_emision"],
        unique=False,
    )

    op.create_table(
        "tbl_retencion_recibida_detalle",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("usuario_auditoria", sa.String(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("retencion_recibida_id", sa.Uuid(), nullable=False),
        sa.Column("codigo_impuesto_sri", sa.String(length=5), nullable=False),
        sa.Column("porcentaje_aplicado", sa.Numeric(7, 4), nullable=False),
        sa.Column("base_imponible", sa.Numeric(12, 2), nullable=False),
        sa.Column("valor_retenido", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["retencion_recibida_id"], ["tbl_retencion_recibida.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tbl_retencion_recibida_detalle_id"),
        "tbl_retencion_recibida_detalle",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_retencion_recibida_detalle_activo"),
        "tbl_retencion_recibida_detalle",
        ["activo"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_retencion_recibida_detalle_created_by"),
        "tbl_retencion_recibida_detalle",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_retencion_recibida_detalle_updated_by"),
        "tbl_retencion_recibida_detalle",
        ["updated_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_retencion_recibida_detalle_retencion_recibida_id"),
        "tbl_retencion_recibida_detalle",
        ["retencion_recibida_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_tbl_retencion_recibida_detalle_retencion_recibida_id"),
        table_name="tbl_retencion_recibida_detalle",
    )
    op.drop_index(
        op.f("ix_tbl_retencion_recibida_detalle_updated_by"),
        table_name="tbl_retencion_recibida_detalle",
    )
    op.drop_index(
        op.f("ix_tbl_retencion_recibida_detalle_created_by"),
        table_name="tbl_retencion_recibida_detalle",
    )
    op.drop_index(
        op.f("ix_tbl_retencion_recibida_detalle_activo"),
        table_name="tbl_retencion_recibida_detalle",
    )
    op.drop_index(
        op.f("ix_tbl_retencion_recibida_detalle_id"),
        table_name="tbl_retencion_recibida_detalle",
    )
    op.drop_table("tbl_retencion_recibida_detalle")

    op.drop_index(op.f("ix_tbl_retencion_recibida_fecha_emision"), table_name="tbl_retencion_recibida")
    op.drop_index(op.f("ix_tbl_retencion_recibida_clave_acceso_sri"), table_name="tbl_retencion_recibida")
    op.drop_index(op.f("ix_tbl_retencion_recibida_cliente_id"), table_name="tbl_retencion_recibida")
    op.drop_index(op.f("ix_tbl_retencion_recibida_venta_id"), table_name="tbl_retencion_recibida")
    op.drop_index(op.f("ix_tbl_retencion_recibida_updated_by"), table_name="tbl_retencion_recibida")
    op.drop_index(op.f("ix_tbl_retencion_recibida_created_by"), table_name="tbl_retencion_recibida")
    op.drop_index(op.f("ix_tbl_retencion_recibida_activo"), table_name="tbl_retencion_recibida")
    op.drop_index(op.f("ix_tbl_retencion_recibida_id"), table_name="tbl_retencion_recibida")
    op.drop_table("tbl_retencion_recibida")
