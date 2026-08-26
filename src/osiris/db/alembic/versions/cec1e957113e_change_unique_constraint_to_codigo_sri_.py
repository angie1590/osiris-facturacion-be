"""change unique constraint to codigo_sri and descripcion

Revision ID: cec1e957113e
Revises: 20f3d9f4a008
Create Date: 2025-11-29 18:08:48.423919

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'cec1e957113e'
down_revision: Union[str, None] = '06ee39e487b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Eliminar índice unique existente en codigo_sri
    op.drop_index('ix_aux_impuesto_catalogo_codigo_sri', table_name='aux_impuesto_catalogo')

    # Recrear como índice no-unique
    op.create_index('ix_aux_impuesto_catalogo_codigo_sri', 'aux_impuesto_catalogo', ['codigo_sri'], unique=False)

    # Crear nueva constraint unique compuesta por codigo_sri + descripcion
    op.create_unique_constraint('uq_impuesto_codigo_descripcion', 'aux_impuesto_catalogo', ['codigo_sri', 'descripcion'])


def downgrade() -> None:
    """Downgrade schema."""
    # Eliminar constraint compuesta
    op.drop_constraint('uq_impuesto_codigo_descripcion', 'aux_impuesto_catalogo', type_='unique')

    # Eliminar índice no-unique
    op.drop_index('ix_aux_impuesto_catalogo_codigo_sri', table_name='aux_impuesto_catalogo')

    # Recrear índice unique original
    op.create_index('ix_aux_impuesto_catalogo_codigo_sri', 'aux_impuesto_catalogo', ['codigo_sri'], unique=True)
