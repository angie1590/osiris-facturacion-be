"""add latitud/longitud to sucursal

Revision ID: 2a7d9b3c4e11
Revises: 1b905be2a0df
Create Date: 2026-02-24 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2a7d9b3c4e11"
down_revision: Union[str, None] = "1b905be2a0df"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tbl_sucursal", sa.Column("latitud", sa.Numeric(9, 6), nullable=True))
    op.add_column("tbl_sucursal", sa.Column("longitud", sa.Numeric(9, 6), nullable=True))

    op.create_check_constraint(
        "ck_sucursal_latitud_rango",
        "tbl_sucursal",
        "(latitud IS NULL OR (latitud >= -90 AND latitud <= 90))",
    )
    op.create_check_constraint(
        "ck_sucursal_longitud_rango",
        "tbl_sucursal",
        "(longitud IS NULL OR (longitud >= -180 AND longitud <= 180))",
    )


def downgrade() -> None:
    op.drop_constraint("ck_sucursal_longitud_rango", "tbl_sucursal", type_="check")
    op.drop_constraint("ck_sucursal_latitud_rango", "tbl_sucursal", type_="check")
    op.drop_column("tbl_sucursal", "longitud")
    op.drop_column("tbl_sucursal", "latitud")
