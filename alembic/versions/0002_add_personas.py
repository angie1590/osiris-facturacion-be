"""add personas table

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    tipo_persona = sa.Enum("cliente", "proveedor", name="tipopersona")

    op.create_table(
        "personas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo", tipo_persona, nullable=False),
        sa.Column(
            "identificacion_tipo",
            sa.Enum("ruc", "cedula", "pasaporte", "consumidor_final", name="identificationtype"),
            nullable=False,
            server_default="ruc",
        ),
        sa.Column("identificacion", sa.String(20), nullable=False),
        sa.Column("razon_social", sa.String(300), nullable=False),
        sa.Column("nombre_comercial", sa.String(300), nullable=True),
        sa.Column("email", sa.String(100), nullable=True),
        sa.Column("telefono", sa.String(20), nullable=True),
        sa.Column("direccion", sa.String(300), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index("ix_personas_empresa_id", "personas", ["empresa_id"])


def downgrade() -> None:
    op.drop_table("personas")
    sa.Enum(name="tipopersona").drop(op.get_bind(), checkfirst=True)
