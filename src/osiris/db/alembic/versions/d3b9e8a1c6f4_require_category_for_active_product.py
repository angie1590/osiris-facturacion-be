"""Require primary category for active products.

Revision ID: d3b9e8a1c6f4
Revises: c8d7e9f1a204
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d3b9e8a1c6f4"
down_revision: Union[str, None] = "c8d7e9f1a204"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE_NAME = "tbl_producto"
CONSTRAINT_NAME = "ck_tbl_producto_active_requires_category"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns(TABLE_NAME)}
    if "activo" not in columns or "categoria_principal_id" not in columns:
        raise RuntimeError(
            "Product category cutover requires activo and categoria_principal_id columns."
        )

    missing_count = bind.execute(
        sa.text(
            f"SELECT count(*) FROM {TABLE_NAME} "
            "WHERE activo IS TRUE AND categoria_principal_id IS NULL"
        )
    ).scalar_one()
    if missing_count:
        raise RuntimeError(
            "Cannot require a primary category: "
            f"{missing_count} active products without a primary category remain."
        )

    existing = {
        constraint["name"]
        for constraint in inspector.get_check_constraints(TABLE_NAME)
    }
    if CONSTRAINT_NAME in existing:
        raise RuntimeError(f"{CONSTRAINT_NAME} already exists.")

    with op.batch_alter_table(TABLE_NAME) as batch:
        batch.create_check_constraint(
            CONSTRAINT_NAME,
            "NOT activo OR categoria_principal_id IS NOT NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    existing = {
        constraint["name"]
        for constraint in sa.inspect(bind).get_check_constraints(TABLE_NAME)
    }
    if CONSTRAINT_NAME not in existing:
        return
    with op.batch_alter_table(TABLE_NAME) as batch:
        batch.drop_constraint(CONSTRAINT_NAME, type_="check")