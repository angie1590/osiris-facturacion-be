"""add codigo_tipo_impuesto to impuesto_catalogo

Revision ID: 6500f1c98911
Revises: 0cd6bb724d55
Create Date: 2025-11-29 12:40:30.217306

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6500f1c98911'
down_revision: Union[str, None] = '0cd6bb724d55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add IRBPNR value to tipoimpuesto enum (requires commit before use)
    conn = op.get_bind()
    conn.execute(sa.text("COMMIT"))
    conn.execute(sa.text("ALTER TYPE tipoimpuesto ADD VALUE IF NOT EXISTS 'IRBPNR'"))
    conn.execute(sa.text("COMMIT"))

    # Add codigo_tipo_impuesto column
    op.add_column('aux_impuesto_catalogo', sa.Column('codigo_tipo_impuesto', sa.String(length=10), nullable=True))

    # Update existing rows with default values based on tipo_impuesto
    op.execute("""
        UPDATE aux_impuesto_catalogo
        SET codigo_tipo_impuesto = CASE tipo_impuesto
            WHEN 'IVA' THEN '2'
            WHEN 'ICE' THEN '3'
            WHEN 'IRBPNR' THEN '5'
        END
    """)

    # Make column NOT NULL and add index
    op.alter_column('aux_impuesto_catalogo', 'codigo_tipo_impuesto', nullable=False)
    op.create_index(op.f('ix_aux_impuesto_catalogo_codigo_tipo_impuesto'), 'aux_impuesto_catalogo', ['codigo_tipo_impuesto'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_aux_impuesto_catalogo_codigo_tipo_impuesto'), table_name='aux_impuesto_catalogo')
    op.drop_column('aux_impuesto_catalogo', 'codigo_tipo_impuesto')
