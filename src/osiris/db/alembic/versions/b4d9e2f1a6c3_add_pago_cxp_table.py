"""add pago cxp table

Revision ID: b4d9e2f1a6c3
Revises: a1c4f8d9e2b7
Create Date: 2026-02-19 21:20:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b4d9e2f1a6c3"
down_revision = "a1c4f8d9e2b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tbl_pago_cxp",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("usuario_auditoria", sa.String(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("cuenta_por_pagar_id", sa.Uuid(), nullable=False),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("forma_pago", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["cuenta_por_pagar_id"], ["tbl_cuenta_por_pagar.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tbl_pago_cxp_id"), "tbl_pago_cxp", ["id"], unique=False)
    op.create_index(op.f("ix_tbl_pago_cxp_activo"), "tbl_pago_cxp", ["activo"], unique=False)
    op.create_index(op.f("ix_tbl_pago_cxp_cuenta_por_pagar_id"), "tbl_pago_cxp", ["cuenta_por_pagar_id"], unique=False)
    op.create_index(op.f("ix_tbl_pago_cxp_fecha"), "tbl_pago_cxp", ["fecha"], unique=False)
    op.create_index(op.f("ix_tbl_pago_cxp_created_by"), "tbl_pago_cxp", ["created_by"], unique=False)
    op.create_index(op.f("ix_tbl_pago_cxp_updated_by"), "tbl_pago_cxp", ["updated_by"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tbl_pago_cxp_updated_by"), table_name="tbl_pago_cxp")
    op.drop_index(op.f("ix_tbl_pago_cxp_created_by"), table_name="tbl_pago_cxp")
    op.drop_index(op.f("ix_tbl_pago_cxp_fecha"), table_name="tbl_pago_cxp")
    op.drop_index(op.f("ix_tbl_pago_cxp_cuenta_por_pagar_id"), table_name="tbl_pago_cxp")
    op.drop_index(op.f("ix_tbl_pago_cxp_activo"), table_name="tbl_pago_cxp")
    op.drop_index(op.f("ix_tbl_pago_cxp_id"), table_name="tbl_pago_cxp")
    op.drop_table("tbl_pago_cxp")
