"""añadir campo foto a empleado

Revision ID: ccbbbb162eef
Revises: 219b76343e08
Create Date: 2025-12-03 05:10:59.872325

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ccbbbb162eef'
down_revision: Union[str, None] = '219b76343e08'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Añadir columna 'foto' a tbl_empleado (nullable)
    op.add_column('tbl_empleado', sa.Column('foto', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remover columna 'foto' de tbl_empleado
    op.drop_column('tbl_empleado', 'foto')
