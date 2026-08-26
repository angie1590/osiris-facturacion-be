"""add rimpe fields to venta

Revision ID: 7a1c9d4e2f10
Revises: e4f6a8b0c2d1
Create Date: 2026-02-19 19:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7a1c9d4e2f10"
down_revision: Union[str, None] = "e4f6a8b0c2d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tbl_venta",
        sa.Column("regimen_emisor", sa.String(length=30), nullable=False, server_default="GENERAL"),
    )
    op.add_column(
        "tbl_venta_detalle",
        sa.Column("es_actividad_excluida", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("tbl_venta_detalle", "es_actividad_excluida")
    op.drop_column("tbl_venta", "regimen_emisor")
