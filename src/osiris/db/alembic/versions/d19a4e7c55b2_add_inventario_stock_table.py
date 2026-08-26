"""add inventario stock materialized table

Revision ID: d19a4e7c55b2
Revises: c7b5a9d8e112
Create Date: 2026-02-19 16:40:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d19a4e7c55b2"
down_revision = "c7b5a9d8e112"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tbl_inventario_stock",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("usuario_auditoria", sa.String(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("bodega_id", sa.Uuid(), nullable=False),
        sa.Column("producto_id", sa.Uuid(), nullable=False),
        sa.Column("cantidad_actual", sa.Numeric(14, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("costo_promedio_vigente", sa.Numeric(14, 4), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["bodega_id"], ["tbl_bodega.id"]),
        sa.ForeignKeyConstraint(["producto_id"], ["tbl_producto.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "bodega_id",
            "producto_id",
            name="uq_tbl_inventario_stock_bodega_producto",
        ),
    )
    op.create_index(op.f("ix_tbl_inventario_stock_id"), "tbl_inventario_stock", ["id"], unique=False)
    op.create_index(op.f("ix_tbl_inventario_stock_activo"), "tbl_inventario_stock", ["activo"], unique=False)
    op.create_index(
        op.f("ix_tbl_inventario_stock_bodega_id"),
        "tbl_inventario_stock",
        ["bodega_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_inventario_stock_producto_id"),
        "tbl_inventario_stock",
        ["producto_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_inventario_stock_created_by"),
        "tbl_inventario_stock",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_inventario_stock_updated_by"),
        "tbl_inventario_stock",
        ["updated_by"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_tbl_inventario_stock_updated_by"), table_name="tbl_inventario_stock")
    op.drop_index(op.f("ix_tbl_inventario_stock_created_by"), table_name="tbl_inventario_stock")
    op.drop_index(op.f("ix_tbl_inventario_stock_producto_id"), table_name="tbl_inventario_stock")
    op.drop_index(op.f("ix_tbl_inventario_stock_bodega_id"), table_name="tbl_inventario_stock")
    op.drop_index(op.f("ix_tbl_inventario_stock_activo"), table_name="tbl_inventario_stock")
    op.drop_index(op.f("ix_tbl_inventario_stock_id"), table_name="tbl_inventario_stock")
    op.drop_table("tbl_inventario_stock")
