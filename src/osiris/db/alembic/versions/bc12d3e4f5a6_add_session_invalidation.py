"""add session invalidation timestamp

Revision ID: bc12d3e4f5a6
Revises: aa10b2c3d4e5
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "bc12d3e4f5a6"
down_revision: Union[str, None] = "aa10b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tbl_usuario", sa.Column("sesion_invalidada_en", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("tbl_usuario", "sesion_invalidada_en")