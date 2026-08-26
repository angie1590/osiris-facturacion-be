"""add empresa tributary fields and audit_log table

Revision ID: e11c0f9a7b21
Revises: d830a262e67a
Create Date: 2026-02-19 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e11c0f9a7b21"
down_revision: Union[str, None] = "d830a262e67a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tbl_empresa",
        sa.Column("regimen", sa.String(length=40), nullable=False, server_default="GENERAL"),
    )
    op.add_column(
        "tbl_empresa",
        sa.Column(
            "modo_emision",
            sa.String(length=40),
            nullable=False,
            server_default="ELECTRONICO",
        ),
    )

    op.create_check_constraint(
        "ck_tbl_empresa_regimen",
        "tbl_empresa",
        "regimen IN ('GENERAL', 'RIMPE_EMPRENDEDOR', 'RIMPE_NEGOCIO_POPULAR')",
    )
    op.create_check_constraint(
        "ck_tbl_empresa_modo_emision",
        "tbl_empresa",
        "modo_emision IN ('ELECTRONICO', 'NOTA_VENTA_FISICA')",
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entidad", sa.String(length=100), nullable=False),
        sa.Column("entidad_id", sa.Uuid(), nullable=False),
        sa.Column("accion", sa.String(length=20), nullable=False),
        sa.Column("estado_anterior", sa.JSON(), nullable=False),
        sa.Column("estado_nuevo", sa.JSON(), nullable=False),
        sa.Column("usuario_auditoria", sa.String(length=255), nullable=True),
        sa.Column(
            "creado_en",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_log_id"), "audit_log", ["id"], unique=False)
    op.create_index(op.f("ix_audit_log_entidad"), "audit_log", ["entidad"], unique=False)
    op.create_index(
        op.f("ix_audit_log_entidad_id"),
        "audit_log",
        ["entidad_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_log_entidad_id"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_entidad"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_id"), table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_constraint("ck_tbl_empresa_modo_emision", "tbl_empresa", type_="check")
    op.drop_constraint("ck_tbl_empresa_regimen", "tbl_empresa", type_="check")
    op.drop_column("tbl_empresa", "modo_emision")
    op.drop_column("tbl_empresa", "regimen")
