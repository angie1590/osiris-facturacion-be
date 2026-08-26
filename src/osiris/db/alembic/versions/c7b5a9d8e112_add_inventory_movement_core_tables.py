"""add inventory movement core tables

Revision ID: c7b5a9d8e112
Revises: 8e2f4c1d9a77
Create Date: 2026-02-19 16:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c7b5a9d8e112"
down_revision = "8e2f4c1d9a77"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tbl_movimiento_inventario",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("usuario_auditoria", sa.String(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("bodega_id", sa.Uuid(), nullable=False),
        sa.Column("tipo_movimiento", sa.String(length=20), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="BORRADOR"),
        sa.Column("referencia_documento", sa.String(length=120), nullable=True),
        sa.ForeignKeyConstraint(["bodega_id"], ["tbl_bodega.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tbl_movimiento_inventario_id"), "tbl_movimiento_inventario", ["id"], unique=False)
    op.create_index(op.f("ix_tbl_movimiento_inventario_activo"), "tbl_movimiento_inventario", ["activo"], unique=False)
    op.create_index(
        op.f("ix_tbl_movimiento_inventario_bodega_id"),
        "tbl_movimiento_inventario",
        ["bodega_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_movimiento_inventario_created_by"),
        "tbl_movimiento_inventario",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_movimiento_inventario_updated_by"),
        "tbl_movimiento_inventario",
        ["updated_by"],
        unique=False,
    )
    op.create_check_constraint(
        "ck_tbl_movimiento_inventario_tipo_movimiento",
        "tbl_movimiento_inventario",
        "tipo_movimiento IN ('INGRESO', 'EGRESO', 'TRANSFERENCIA', 'AJUSTE')",
    )
    op.create_check_constraint(
        "ck_tbl_movimiento_inventario_estado",
        "tbl_movimiento_inventario",
        "estado IN ('BORRADOR', 'CONFIRMADO', 'ANULADO')",
    )

    op.create_table(
        "tbl_movimiento_inventario_detalle",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("usuario_auditoria", sa.String(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("movimiento_inventario_id", sa.Uuid(), nullable=False),
        sa.Column("producto_id", sa.Uuid(), nullable=False),
        sa.Column("cantidad", sa.Numeric(14, 4), nullable=False),
        sa.Column("costo_unitario", sa.Numeric(14, 4), nullable=False),
        sa.ForeignKeyConstraint(["movimiento_inventario_id"], ["tbl_movimiento_inventario.id"]),
        sa.ForeignKeyConstraint(["producto_id"], ["tbl_producto.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tbl_movimiento_inventario_detalle_id"),
        "tbl_movimiento_inventario_detalle",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_movimiento_inventario_detalle_activo"),
        "tbl_movimiento_inventario_detalle",
        ["activo"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_movimiento_inventario_detalle_movimiento_inventario_id"),
        "tbl_movimiento_inventario_detalle",
        ["movimiento_inventario_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_movimiento_inventario_detalle_producto_id"),
        "tbl_movimiento_inventario_detalle",
        ["producto_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_movimiento_inventario_detalle_created_by"),
        "tbl_movimiento_inventario_detalle",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_movimiento_inventario_detalle_updated_by"),
        "tbl_movimiento_inventario_detalle",
        ["updated_by"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_tbl_movimiento_inventario_detalle_updated_by"),
        table_name="tbl_movimiento_inventario_detalle",
    )
    op.drop_index(
        op.f("ix_tbl_movimiento_inventario_detalle_created_by"),
        table_name="tbl_movimiento_inventario_detalle",
    )
    op.drop_index(
        op.f("ix_tbl_movimiento_inventario_detalle_producto_id"),
        table_name="tbl_movimiento_inventario_detalle",
    )
    op.drop_index(
        op.f("ix_tbl_movimiento_inventario_detalle_movimiento_inventario_id"),
        table_name="tbl_movimiento_inventario_detalle",
    )
    op.drop_index(
        op.f("ix_tbl_movimiento_inventario_detalle_activo"),
        table_name="tbl_movimiento_inventario_detalle",
    )
    op.drop_index(
        op.f("ix_tbl_movimiento_inventario_detalle_id"),
        table_name="tbl_movimiento_inventario_detalle",
    )
    op.drop_table("tbl_movimiento_inventario_detalle")

    op.drop_constraint(
        "ck_tbl_movimiento_inventario_estado",
        "tbl_movimiento_inventario",
        type_="check",
    )
    op.drop_constraint(
        "ck_tbl_movimiento_inventario_tipo_movimiento",
        "tbl_movimiento_inventario",
        type_="check",
    )
    op.drop_index(
        op.f("ix_tbl_movimiento_inventario_updated_by"),
        table_name="tbl_movimiento_inventario",
    )
    op.drop_index(
        op.f("ix_tbl_movimiento_inventario_created_by"),
        table_name="tbl_movimiento_inventario",
    )
    op.drop_index(
        op.f("ix_tbl_movimiento_inventario_bodega_id"),
        table_name="tbl_movimiento_inventario",
    )
    op.drop_index(
        op.f("ix_tbl_movimiento_inventario_activo"),
        table_name="tbl_movimiento_inventario",
    )
    op.drop_index(
        op.f("ix_tbl_movimiento_inventario_id"),
        table_name="tbl_movimiento_inventario",
    )
    op.drop_table("tbl_movimiento_inventario")
