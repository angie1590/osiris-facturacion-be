"""add approval code hash to users

Revision ID: cd23e4f5a6b7
Revises: bc12d3e4f5a6
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "cd23e4f5a6b7"
down_revision: Union[str, None] = "bc12d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tbl_usuario", sa.Column("codigo_aprobacion_hash", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("tbl_usuario", "codigo_aprobacion_hash")