"""add sucursal matriz constraints

Revision ID: 5481adce2db3
Revises: e3f9a7c1d2b4
Create Date: 2026-02-22 11:20:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "5481adce2db3"
down_revision: Union[str, None] = "e3f9a7c1d2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_unique_constraint(table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return constraint_name in {
        constraint["name"] for constraint in inspector.get_unique_constraints(table_name)
    }


def _has_check_constraint(table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return constraint_name in {
        constraint["name"] for constraint in inspector.get_check_constraints(table_name)
    }


def upgrade() -> None:
    # Normaliza data legacy antes de imponer el check.
    op.execute(
        sa.text(
            "UPDATE tbl_sucursal "
            "SET es_matriz = CASE WHEN codigo = '001' THEN true ELSE false END"
        )
    )

    if not _has_unique_constraint("tbl_sucursal", "uq_sucursal_empresa_codigo"):
        op.create_unique_constraint(
            "uq_sucursal_empresa_codigo",
            "tbl_sucursal",
            ["empresa_id", "codigo"],
        )

    if not _has_check_constraint("tbl_sucursal", "ck_sucursal_matriz_codigo"):
        op.create_check_constraint(
            "ck_sucursal_matriz_codigo",
            "tbl_sucursal",
            "(codigo = '001' AND es_matriz = true) OR (codigo != '001' AND es_matriz = false)",
        )


def downgrade() -> None:
    if _has_check_constraint("tbl_sucursal", "ck_sucursal_matriz_codigo"):
        op.drop_constraint("ck_sucursal_matriz_codigo", "tbl_sucursal", type_="check")

    if _has_unique_constraint("tbl_sucursal", "uq_sucursal_empresa_codigo"):
        op.drop_constraint("uq_sucursal_empresa_codigo", "tbl_sucursal", type_="unique")

