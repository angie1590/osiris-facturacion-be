"""add_config_impresion_to_punto_emision

Revision ID: a1b2c3d4e5f6
Revises: 9c4d2e7a6b11
Create Date: 2026-02-22 16:18:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "9c4d2e7a6b11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tbl_punto_emision",
        sa.Column(
            "config_impresion",
            sa.JSON(),
            nullable=False,
            server_default=sa.text(
                '\'{"margen_superior_cm": 5.0, "max_items_por_pagina": 15}\'::json'
            ),
        ),
    )
    op.alter_column("tbl_punto_emision", "config_impresion", server_default=None)


def downgrade() -> None:
    op.drop_column("tbl_punto_emision", "config_impresion")

