"""create tbl_categoria

Revision ID: c1f2d3e4b5a6
Revises: f277a59033e3
Create Date: 2025-11-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'c1f2d3e4b5a6'
down_revision: Union[str, None] = 'f277a59033e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('tbl_categoria',
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('creado_en', sa.DateTime(), nullable=False),
    sa.Column('actualizado_en', sa.DateTime(), nullable=False),
    sa.Column('usuario_auditoria', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('nombre', sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
    sa.Column('es_padre', sa.Boolean(), nullable=False),
    sa.Column('parent_id', sa.Uuid(), nullable=True),
    sa.ForeignKeyConstraint(['parent_id'], ['tbl_categoria.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tbl_categoria_activo'), 'tbl_categoria', ['activo'], unique=False)
    op.create_index(op.f('ix_tbl_categoria_id'), 'tbl_categoria', ['id'], unique=False)
    op.create_index(op.f('ix_tbl_categoria_parent_id'), 'tbl_categoria', ['parent_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_tbl_categoria_parent_id'), table_name='tbl_categoria')
    op.drop_index(op.f('ix_tbl_categoria_id'), table_name='tbl_categoria')
    op.drop_index(op.f('ix_tbl_categoria_activo'), table_name='tbl_categoria')
    op.drop_table('tbl_categoria')
