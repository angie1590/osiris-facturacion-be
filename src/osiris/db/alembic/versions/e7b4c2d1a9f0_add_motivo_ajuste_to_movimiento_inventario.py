"""add motivo_ajuste column to movimiento inventario

Revision ID: e7b4c2d1a9f0
Revises: d19a4e7c55b2
Create Date: 2026-02-19 19:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e7b4c2d1a9f0"
down_revision = "d19a4e7c55b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tbl_movimiento_inventario",
        sa.Column("motivo_ajuste", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tbl_movimiento_inventario", "motivo_ajuste")
