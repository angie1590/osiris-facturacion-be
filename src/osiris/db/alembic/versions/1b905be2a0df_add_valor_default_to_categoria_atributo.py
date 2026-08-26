"""add valor_default to categoria_atributo

Revision ID: 1b905be2a0df
Revises: 2485b897f986
Create Date: 2026-02-22 23:30:53.482759

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1b905be2a0df"
down_revision: Union[str, None] = "2485b897f986"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tbl_categoria_atributo",
        sa.Column("valor_default", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tbl_categoria_atributo", "valor_default")
