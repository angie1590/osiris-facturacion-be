"""Store reversible attribute definition and value snapshots.

Revision ID: c5e91a7d2b64
Revises: d4a8c2f19e63
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c5e91a7d2b64"
down_revision = "d4a8c2f19e63"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tbl_atributo_cambio",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("usuario_auditoria", sa.String(length=255), nullable=True),
        sa.Column("atributo_id", sa.Uuid(), nullable=False),
        sa.Column("operacion", sa.String(length=20), nullable=False),
        sa.Column("definicion_anterior", sa.JSON(), nullable=False),
        sa.Column("definicion_posterior", sa.JSON(), nullable=False),
        sa.Column("asignaciones_anteriores", sa.JSON(), nullable=False),
        sa.Column("asignaciones_posteriores", sa.JSON(), nullable=False),
        sa.Column("valores_anteriores", sa.JSON(), nullable=False),
        sa.Column("valores_posteriores", sa.JSON(), nullable=False),
        sa.Column("remapeos_anteriores", sa.JSON(), nullable=False),
        sa.Column("remapeos_posteriores", sa.JSON(), nullable=False),
        sa.Column("revertido", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("revertido_en", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["atributo_id"], ["tbl_atributo.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tbl_atributo_cambio_atributo_id", "tbl_atributo_cambio", ["atributo_id"]
    )
    op.create_index(
        "ix_tbl_atributo_cambio_revertido", "tbl_atributo_cambio", ["revertido"]
    )


def downgrade() -> None:
    pending = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT id FROM tbl_atributo_cambio WHERE revertido = false LIMIT 1"
            )
        )
        .first()
    )
    if pending:
        raise RuntimeError(
            "Cannot downgrade while unreverted attribute snapshots would be lost."
        )
    op.drop_index("ix_tbl_atributo_cambio_revertido", table_name="tbl_atributo_cambio")
    op.drop_index(
        "ix_tbl_atributo_cambio_atributo_id", table_name="tbl_atributo_cambio"
    )
    op.drop_table("tbl_atributo_cambio")
