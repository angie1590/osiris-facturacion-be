"""agregar descripcion y codigo_barras a producto

Revision ID: 8f3a2b1c4d5e
Revises: 62b7917189d0
Create Date: 2025-12-02 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f3a2b1c4d5e'
down_revision: Union[str, None] = '62b7917189d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Agregar campos descripcion y codigo_barras a tbl_producto."""
    op.add_column('tbl_producto', sa.Column('descripcion', sa.String(length=1000), nullable=True))
    op.add_column('tbl_producto', sa.Column('codigo_barras', sa.String(length=100), nullable=True))
    op.create_index(op.f('ix_tbl_producto_codigo_barras'), 'tbl_producto', ['codigo_barras'], unique=False)


def downgrade() -> None:
    """Revertir cambios."""
    op.drop_index(op.f('ix_tbl_producto_codigo_barras'), table_name='tbl_producto')
    op.drop_column('tbl_producto', 'codigo_barras')
    op.drop_column('tbl_producto', 'descripcion')
