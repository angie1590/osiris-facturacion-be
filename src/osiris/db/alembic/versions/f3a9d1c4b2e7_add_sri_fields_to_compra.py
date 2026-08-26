"""add sri mandatory fields to compra

Revision ID: f3a9d1c4b2e7
Revises: e7b4c2d1a9f0
Create Date: 2026-02-19 20:20:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f3a9d1c4b2e7"
down_revision = "e7b4c2d1a9f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tbl_compra",
        sa.Column(
            "proveedor_id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("'00000000-0000-0000-0000-000000000000'"),
        ),
    )
    op.add_column(
        "tbl_compra",
        sa.Column(
            "secuencial_factura",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'000-000-000000000'"),
        ),
    )
    op.add_column(
        "tbl_compra",
        sa.Column(
            "autorizacion_sri",
            sa.String(length=49),
            nullable=False,
            server_default=sa.text("'0000000000000000000000000000000000000'"),
        ),
    )
    op.add_column(
        "tbl_compra",
        sa.Column(
            "sustento_tributario",
            sa.String(length=5),
            nullable=False,
            server_default=sa.text("'01'"),
        ),
    )

    op.create_index(op.f("ix_tbl_compra_proveedor_id"), "tbl_compra", ["proveedor_id"], unique=False)
    op.create_index(op.f("ix_tbl_compra_secuencial_factura"), "tbl_compra", ["secuencial_factura"], unique=False)
    op.create_index(op.f("ix_tbl_compra_autorizacion_sri"), "tbl_compra", ["autorizacion_sri"], unique=False)

    op.alter_column("tbl_compra", "estado", server_default=sa.text("'BORRADOR'"))
    op.alter_column("tbl_compra", "proveedor_id", server_default=None)
    op.alter_column("tbl_compra", "secuencial_factura", server_default=None)
    op.alter_column("tbl_compra", "autorizacion_sri", server_default=None)
    op.alter_column("tbl_compra", "sustento_tributario", server_default=None)


def downgrade() -> None:
    op.alter_column("tbl_compra", "estado", server_default=sa.text("'PENDIENTE'"))
    op.drop_index(op.f("ix_tbl_compra_autorizacion_sri"), table_name="tbl_compra")
    op.drop_index(op.f("ix_tbl_compra_secuencial_factura"), table_name="tbl_compra")
    op.drop_index(op.f("ix_tbl_compra_proveedor_id"), table_name="tbl_compra")
    op.drop_column("tbl_compra", "sustento_tributario")
    op.drop_column("tbl_compra", "autorizacion_sri")
    op.drop_column("tbl_compra", "secuencial_factura")
    op.drop_column("tbl_compra", "proveedor_id")
