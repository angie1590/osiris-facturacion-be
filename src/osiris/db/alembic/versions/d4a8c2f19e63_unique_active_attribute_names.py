"""Enforce globally unique active attribute names.

Revision ID: d4a8c2f19e63
Revises: c6f9d3a1b285
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "d4a8c2f19e63"
down_revision = "c6f9d3a1b285"
branch_labels = None
depends_on = None

INDEX_NAME = "uq_tbl_atributo_nombre_activo_normalized"


def _duplicate_active_names() -> list[tuple[str, int]]:
    bind = op.get_bind()
    attributes = sa.table(
        "tbl_atributo",
        sa.column("nombre", sa.String()),
        sa.column("activo", sa.Boolean()),
    )
    normalized_name = sa.func.lower(sa.func.trim(attributes.c.nombre)).label("nombre")
    rows = bind.execute(
        sa.select(normalized_name, sa.func.count().label("total"))
        .where(attributes.c.activo.is_(True))
        .group_by(normalized_name)
        .having(sa.func.count() > 1)
        .order_by(normalized_name)
        .limit(20)
    ).all()
    return [(str(row.nombre), int(row.total)) for row in rows]


def upgrade() -> None:
    duplicates = _duplicate_active_names()
    if duplicates:
        details = ", ".join(f"{name} ({total})" for name, total in duplicates)
        raise RuntimeError(
            "Cannot enforce globally unique active attribute names; "
            f"deactivate or rename duplicates first: {details}"
        )

    op.create_index(
        INDEX_NAME,
        "tbl_atributo",
        [sa.text("lower(trim(nombre))")],
        unique=True,
        postgresql_where=sa.text("activo IS TRUE"),
        sqlite_where=sa.text("activo = 1"),
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="tbl_atributo")