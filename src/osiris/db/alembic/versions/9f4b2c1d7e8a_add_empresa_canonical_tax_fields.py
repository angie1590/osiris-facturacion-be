"""add canonical tax fields to empresa

Revision ID: 9f4b2c1d7e8a
Revises: cd23e4f5a6b7
Create Date: 2026-08-28 10:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "9f4b2c1d7e8a"
down_revision: Union[str, None] = "cd23e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _has_check_constraint(table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return constraint_name in {
        constraint["name"] for constraint in inspector.get_check_constraints(table_name)
    }


def upgrade() -> None:
    if not _has_column("tbl_empresa", "email"):
        op.add_column("tbl_empresa", sa.Column("email", sa.String(length=255), nullable=True))

    if not _has_column("tbl_empresa", "tipo_contribuyente_juridico"):
        op.add_column(
            "tbl_empresa",
            sa.Column("tipo_contribuyente_juridico", sa.String(length=32), nullable=True),
        )

    if not _has_column("tbl_empresa", "contribuyente_especial"):
        op.add_column(
            "tbl_empresa",
            sa.Column("contribuyente_especial", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
        op.alter_column("tbl_empresa", "contribuyente_especial", server_default=None)

    if not _has_column("tbl_empresa", "contribuyente_especial_resolucion"):
        op.add_column(
            "tbl_empresa",
            sa.Column("contribuyente_especial_resolucion", sa.String(length=64), nullable=True),
        )

    if not _has_column("tbl_empresa", "gran_contribuyente"):
        op.add_column(
            "tbl_empresa",
            sa.Column("gran_contribuyente", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
        op.alter_column("tbl_empresa", "gran_contribuyente", server_default=None)

    if not _has_column("tbl_empresa", "gran_contribuyente_resolucion"):
        op.add_column(
            "tbl_empresa",
            sa.Column("gran_contribuyente_resolucion", sa.String(length=64), nullable=True),
        )

    if not _has_column("tbl_empresa", "agente_retencion"):
        op.add_column(
            "tbl_empresa",
            sa.Column("agente_retencion", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
        op.alter_column("tbl_empresa", "agente_retencion", server_default=None)

    if not _has_column("tbl_empresa", "agente_retencion_resolucion"):
        op.add_column(
            "tbl_empresa",
            sa.Column("agente_retencion_resolucion", sa.String(length=64), nullable=True),
        )

    # Backfill no destructivo desde tipo_contribuyente_id legacy.
    op.execute(
        sa.text(
            """
            UPDATE tbl_empresa
            SET
                tipo_contribuyente_juridico = CASE
                    WHEN tipo_contribuyente_id = '01' THEN 'PERSONA_NATURAL'
                    WHEN tipo_contribuyente_id = '02' THEN 'SOCIEDAD'
                    ELSE tipo_contribuyente_juridico
                END,
                regimen = CASE
                    WHEN tipo_contribuyente_id = '03' THEN 'RIMPE_NEGOCIO_POPULAR'
                    WHEN tipo_contribuyente_id = '04' THEN 'RIMPE_EMPRENDEDOR'
                    ELSE regimen
                END,
                gran_contribuyente = CASE
                    WHEN tipo_contribuyente_id = '05' THEN true
                    ELSE gran_contribuyente
                END
            """
        )
    )

    # Normalización de resoluciones vacías.
    op.execute(
        sa.text(
            """
            UPDATE tbl_empresa
            SET
                contribuyente_especial_resolucion = NULLIF(trim(contribuyente_especial_resolucion), ''),
                gran_contribuyente_resolucion = NULLIF(trim(gran_contribuyente_resolucion), ''),
                agente_retencion_resolucion = NULLIF(trim(agente_retencion_resolucion), '')
            """
        )
    )

    if not _has_check_constraint("tbl_empresa", "ck_tbl_empresa_tipo_contribuyente_juridico"):
        op.create_check_constraint(
            "ck_tbl_empresa_tipo_contribuyente_juridico",
            "tbl_empresa",
            "tipo_contribuyente_juridico IS NULL OR tipo_contribuyente_juridico IN ('PERSONA_NATURAL', 'SOCIEDAD')",
        )

    if not _has_check_constraint("tbl_empresa", "ck_tbl_empresa_tipo_juridico_regimen"):
        op.create_check_constraint(
            "ck_tbl_empresa_tipo_juridico_regimen",
            "tbl_empresa",
            "NOT (tipo_contribuyente_juridico = 'SOCIEDAD' AND regimen = 'RIMPE_NEGOCIO_POPULAR')",
        )

    if not _has_check_constraint("tbl_empresa", "ck_tbl_empresa_contribuyente_especial_resolucion"):
        op.create_check_constraint(
            "ck_tbl_empresa_contribuyente_especial_resolucion",
            "tbl_empresa",
            "(contribuyente_especial = false AND contribuyente_especial_resolucion IS NULL) OR "
            "(contribuyente_especial = true AND trim(coalesce(contribuyente_especial_resolucion, '')) <> '')",
        )

    if not _has_check_constraint("tbl_empresa", "ck_tbl_empresa_gran_contribuyente_resolucion"):
        op.create_check_constraint(
            "ck_tbl_empresa_gran_contribuyente_resolucion",
            "tbl_empresa",
            "(gran_contribuyente = false AND gran_contribuyente_resolucion IS NULL) OR "
            "(gran_contribuyente = true AND trim(coalesce(gran_contribuyente_resolucion, '')) <> '')",
        )

    if not _has_check_constraint("tbl_empresa", "ck_tbl_empresa_agente_retencion_resolucion"):
        op.create_check_constraint(
            "ck_tbl_empresa_agente_retencion_resolucion",
            "tbl_empresa",
            "(agente_retencion = false AND agente_retencion_resolucion IS NULL) OR "
            "(agente_retencion = true AND trim(coalesce(agente_retencion_resolucion, '')) <> '')",
        )


def downgrade() -> None:
    if _has_check_constraint("tbl_empresa", "ck_tbl_empresa_agente_retencion_resolucion"):
        op.drop_constraint("ck_tbl_empresa_agente_retencion_resolucion", "tbl_empresa", type_="check")

    if _has_check_constraint("tbl_empresa", "ck_tbl_empresa_gran_contribuyente_resolucion"):
        op.drop_constraint("ck_tbl_empresa_gran_contribuyente_resolucion", "tbl_empresa", type_="check")

    if _has_check_constraint("tbl_empresa", "ck_tbl_empresa_contribuyente_especial_resolucion"):
        op.drop_constraint("ck_tbl_empresa_contribuyente_especial_resolucion", "tbl_empresa", type_="check")

    if _has_check_constraint("tbl_empresa", "ck_tbl_empresa_tipo_juridico_regimen"):
        op.drop_constraint("ck_tbl_empresa_tipo_juridico_regimen", "tbl_empresa", type_="check")

    if _has_check_constraint("tbl_empresa", "ck_tbl_empresa_tipo_contribuyente_juridico"):
        op.drop_constraint("ck_tbl_empresa_tipo_contribuyente_juridico", "tbl_empresa", type_="check")

    if _has_column("tbl_empresa", "agente_retencion_resolucion"):
        op.drop_column("tbl_empresa", "agente_retencion_resolucion")

    if _has_column("tbl_empresa", "agente_retencion"):
        op.drop_column("tbl_empresa", "agente_retencion")

    if _has_column("tbl_empresa", "gran_contribuyente_resolucion"):
        op.drop_column("tbl_empresa", "gran_contribuyente_resolucion")

    if _has_column("tbl_empresa", "gran_contribuyente"):
        op.drop_column("tbl_empresa", "gran_contribuyente")

    if _has_column("tbl_empresa", "contribuyente_especial_resolucion"):
        op.drop_column("tbl_empresa", "contribuyente_especial_resolucion")

    if _has_column("tbl_empresa", "contribuyente_especial"):
        op.drop_column("tbl_empresa", "contribuyente_especial")

    if _has_column("tbl_empresa", "tipo_contribuyente_juridico"):
        op.drop_column("tbl_empresa", "tipo_contribuyente_juridico")

    if _has_column("tbl_empresa", "email"):
        op.drop_column("tbl_empresa", "email")
