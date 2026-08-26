"""add empleado.foto column

Revision ID: d830a262e67a
Revises: ccbbbb162eef
Create Date: 2025-12-03 05:26:08.212180

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = 'd830a262e67a'
down_revision: Union[str, None] = 'ccbbbb162eef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    columns = {col['name'] for col in inspector.get_columns('tbl_empleado')}
    if 'foto' not in columns:
        op.add_column('tbl_empleado', sa.Column('foto', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    columns = {col['name'] for col in inspector.get_columns('tbl_empleado')}
    if 'foto' in columns:
        op.drop_column('tbl_empleado', 'foto')
