"""add punto emision secuencial table

Revision ID: f9a7b21c3d4e
Revises: e11c0f9a7b21
Create Date: 2026-02-19 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f9a7b21c3d4e"
down_revision: Union[str, None] = "e11c0f9a7b21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tbl_punto_emision_secuencial",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("usuario_auditoria", sa.String(length=255), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("punto_emision_id", sa.Uuid(), nullable=False),
        sa.Column("tipo_documento", sa.String(length=40), nullable=False),
        sa.Column("secuencial_actual", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["punto_emision_id"], ["tbl_punto_emision.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "punto_emision_id",
            "tipo_documento",
            name="uq_pe_secuencial_punto_tipo_documento",
        ),
    )
    op.create_index(
        op.f("ix_tbl_punto_emision_secuencial_punto_emision_id"),
        "tbl_punto_emision_secuencial",
        ["punto_emision_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_punto_emision_secuencial_tipo_documento"),
        "tbl_punto_emision_secuencial",
        ["tipo_documento"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_punto_emision_secuencial_activo"),
        "tbl_punto_emision_secuencial",
        ["activo"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_punto_emision_secuencial_id"),
        "tbl_punto_emision_secuencial",
        ["id"],
        unique=False,
    )
    op.create_check_constraint(
        "ck_tbl_pe_secuencial_tipo_documento",
        "tbl_punto_emision_secuencial",
        (
            "tipo_documento IN ('FACTURA', 'RETENCION', 'NOTA_CREDITO', "
            "'NOTA_DEBITO', 'GUIA_REMISION')"
        ),
    )
    op.create_check_constraint(
        "ck_tbl_pe_secuencial_actual",
        "tbl_punto_emision_secuencial",
        "secuencial_actual >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_tbl_pe_secuencial_actual", "tbl_punto_emision_secuencial", type_="check")
    op.drop_constraint("ck_tbl_pe_secuencial_tipo_documento", "tbl_punto_emision_secuencial", type_="check")
    op.drop_index(op.f("ix_tbl_punto_emision_secuencial_id"), table_name="tbl_punto_emision_secuencial")
    op.drop_index(op.f("ix_tbl_punto_emision_secuencial_activo"), table_name="tbl_punto_emision_secuencial")
    op.drop_index(op.f("ix_tbl_punto_emision_secuencial_tipo_documento"), table_name="tbl_punto_emision_secuencial")
    op.drop_index(op.f("ix_tbl_punto_emision_secuencial_punto_emision_id"), table_name="tbl_punto_emision_secuencial")
    op.drop_table("tbl_punto_emision_secuencial")
