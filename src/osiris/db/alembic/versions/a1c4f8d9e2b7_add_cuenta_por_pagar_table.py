"""add cuenta por pagar table

Revision ID: a1c4f8d9e2b7
Revises: f3a9d1c4b2e7
Create Date: 2026-02-19 20:50:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1c4f8d9e2b7"
down_revision = "f3a9d1c4b2e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tbl_cuenta_por_pagar",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("usuario_auditoria", sa.String(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("compra_id", sa.Uuid(), nullable=False),
        sa.Column("valor_total_factura", sa.Numeric(12, 2), nullable=False),
        sa.Column("valor_retenido", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("pagos_acumulados", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("saldo_pendiente", sa.Numeric(12, 2), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default=sa.text("'PENDIENTE'")),
        sa.ForeignKeyConstraint(["compra_id"], ["tbl_compra.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("compra_id"),
    )
    op.create_index(op.f("ix_tbl_cuenta_por_pagar_id"), "tbl_cuenta_por_pagar", ["id"], unique=False)
    op.create_index(op.f("ix_tbl_cuenta_por_pagar_activo"), "tbl_cuenta_por_pagar", ["activo"], unique=False)
    op.create_index(op.f("ix_tbl_cuenta_por_pagar_compra_id"), "tbl_cuenta_por_pagar", ["compra_id"], unique=False)
    op.create_index(op.f("ix_tbl_cuenta_por_pagar_created_by"), "tbl_cuenta_por_pagar", ["created_by"], unique=False)
    op.create_index(op.f("ix_tbl_cuenta_por_pagar_updated_by"), "tbl_cuenta_por_pagar", ["updated_by"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tbl_cuenta_por_pagar_updated_by"), table_name="tbl_cuenta_por_pagar")
    op.drop_index(op.f("ix_tbl_cuenta_por_pagar_created_by"), table_name="tbl_cuenta_por_pagar")
    op.drop_index(op.f("ix_tbl_cuenta_por_pagar_compra_id"), table_name="tbl_cuenta_por_pagar")
    op.drop_index(op.f("ix_tbl_cuenta_por_pagar_activo"), table_name="tbl_cuenta_por_pagar")
    op.drop_index(op.f("ix_tbl_cuenta_por_pagar_id"), table_name="tbl_cuenta_por_pagar")
    op.drop_table("tbl_cuenta_por_pagar")
