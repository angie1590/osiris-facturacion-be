"""seed_tipo_contribuyente

Revision ID: 483805449635
Revises: 34c363629f4f
Create Date: 2025-11-27 16:55:41.338379

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

ROWS = [
    {
        "codigo": "01",
        "nombre": "Persona Natural",
        "descripcion": "Persona natural que puede o no llevar contabilidad.",
        "activo": True,
    },
    {
        "codigo": "02",
        "nombre": "Sociedad",
        "descripcion": "Compañía legalmente constituida, obligada a llevar contabilidad.",
        "activo": True,
    },
    {
        "codigo": "03",
        "nombre": "RIMPE – Negocio Popular",
        "descripcion": "Persona natural con ingresos anuales hasta $20,000.",
        "activo": True,
    },
    {
        "codigo": "04",
        "nombre": "RIMPE – Emprendedor",
        "descripcion": "Persona natural o jurídica con ingresos hasta $300,000.",
        "activo": True,
    },
    {
        "codigo": "05",
        "nombre": "Gran Contribuyente",
        "descripcion": "Designado por el SRI por su volumen de actividad.",
        "activo": True,
    },
]


# revision identifiers, used by Alembic.
revision: str = '483805449635'
down_revision: Union[str, None] = '34c363629f4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Insert seed rows without querying the database in offline mode."""
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO aux_tipo_contribuyente "
            "(codigo, nombre, descripcion, activo) "
            "VALUES (:codigo, :nombre, :descripcion, :activo) "
            "ON CONFLICT (codigo) DO NOTHING"
        ),
        ROWS,
    )


def downgrade() -> None:
    """Remove seeded rows (only those we added)."""
    contributors = sa.table(
        "aux_tipo_contribuyente",
        sa.column("codigo", sa.String()),
    )
    op.get_bind().execute(
        sa.delete(contributors).where(
            contributors.c.codigo.in_([row["codigo"] for row in ROWS])
        )
    )
