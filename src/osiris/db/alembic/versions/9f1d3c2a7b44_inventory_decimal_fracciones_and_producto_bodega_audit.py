"""inventory decimal fracciones and producto bodega audit

Revision ID: 9f1d3c2a7b44
Revises: 2a7d9b3c4e11
Create Date: 2026-02-24 16:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9f1d3c2a7b44"
down_revision = "2a7d9b3c4e11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "tbl_producto",
        "cantidad",
        existing_type=sa.INTEGER(),
        type_=sa.Numeric(14, 4),
        existing_nullable=False,
        postgresql_using="cantidad::numeric(14,4)",
    )
    op.add_column(
        "tbl_producto",
        sa.Column("permite_fracciones", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.alter_column(
        "tbl_producto_bodega",
        "cantidad",
        existing_type=sa.INTEGER(),
        type_=sa.Numeric(14, 4),
        existing_nullable=False,
        postgresql_using="cantidad::numeric(14,4)",
    )
    op.add_column(
        "tbl_producto_bodega",
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.add_column(
        "tbl_producto_bodega",
        sa.Column("actualizado_en", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.add_column("tbl_producto_bodega", sa.Column("created_by", sa.String(length=255), nullable=True))
    op.add_column("tbl_producto_bodega", sa.Column("updated_by", sa.String(length=255), nullable=True))
    op.add_column("tbl_producto_bodega", sa.Column("usuario_auditoria", sa.String(), nullable=True))
    op.add_column(
        "tbl_producto_bodega",
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(op.f("ix_tbl_producto_bodega_activo"), "tbl_producto_bodega", ["activo"], unique=False)
    op.create_index(op.f("ix_tbl_producto_bodega_created_by"), "tbl_producto_bodega", ["created_by"], unique=False)
    op.create_index(op.f("ix_tbl_producto_bodega_updated_by"), "tbl_producto_bodega", ["updated_by"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tbl_producto_bodega_updated_by"), table_name="tbl_producto_bodega")
    op.drop_index(op.f("ix_tbl_producto_bodega_created_by"), table_name="tbl_producto_bodega")
    op.drop_index(op.f("ix_tbl_producto_bodega_activo"), table_name="tbl_producto_bodega")

    op.drop_column("tbl_producto_bodega", "activo")
    op.drop_column("tbl_producto_bodega", "usuario_auditoria")
    op.drop_column("tbl_producto_bodega", "updated_by")
    op.drop_column("tbl_producto_bodega", "created_by")
    op.drop_column("tbl_producto_bodega", "actualizado_en")
    op.drop_column("tbl_producto_bodega", "creado_en")

    op.alter_column(
        "tbl_producto_bodega",
        "cantidad",
        existing_type=sa.Numeric(14, 4),
        type_=sa.INTEGER(),
        existing_nullable=False,
        postgresql_using="round(cantidad)::integer",
    )

    op.drop_column("tbl_producto", "permite_fracciones")
    op.alter_column(
        "tbl_producto",
        "cantidad",
        existing_type=sa.Numeric(14, 4),
        type_=sa.INTEGER(),
        existing_nullable=False,
        postgresql_using="round(cantidad)::integer",
    )
