"""Add explicitly approved supplier applicability to taxpayer catalog.

Revision ID: f8b2c5d30e71
Revises: e7a1b4c29d60
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "f8b2c5d30e71"
down_revision = "e7a1b4c29d60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("aux_tipo_contribuyente") as batch:
        batch.add_column(sa.Column("aplica_persona_natural", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("aplica_sociedad", sa.Boolean(), nullable=False, server_default=sa.false()))
    catalog = sa.table(
        "aux_tipo_contribuyente",
        sa.column("codigo", sa.String()),
        sa.column("aplica_persona_natural", sa.Boolean()),
        sa.column("aplica_sociedad", sa.Boolean()),
    )
    connection = op.get_bind()
    connection.execute(catalog.update().where(catalog.c.codigo.in_(["01", "03", "04"])).values(aplica_persona_natural=True))
    connection.execute(catalog.update().where(catalog.c.codigo.in_(["02", "04", "05"])).values(aplica_sociedad=True))


def downgrade() -> None:
    with op.batch_alter_table("aux_tipo_contribuyente") as batch:
        batch.drop_column("aplica_sociedad")
        batch.drop_column("aplica_persona_natural")