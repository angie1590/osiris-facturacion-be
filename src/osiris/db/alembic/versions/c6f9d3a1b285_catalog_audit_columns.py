"""Add standard audit actor columns to catalog tables.

Revision ID: c6f9d3a1b285
Revises: b0d4e7f52a93
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "c6f9d3a1b285"
down_revision = "b0d4e7f52a93"
branch_labels = None
depends_on = None

TABLES = ("tbl_catalogo", "tbl_catalogo_valor")
AUDIT_COLUMNS = ("created_by", "updated_by")


def upgrade() -> None:
    bind = op.get_bind()
    for table_name in TABLES:
        inspector = sa.inspect(bind)
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        for column_name in AUDIT_COLUMNS:
            if column_name not in columns:
                op.add_column(
                    table_name,
                    sa.Column(column_name, sa.String(length=255), nullable=True),
                )

        indexes = {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}
        for column_name in AUDIT_COLUMNS:
            index_name = f"ix_{table_name}_{column_name}"
            if index_name not in indexes:
                op.create_index(index_name, table_name, [column_name], unique=False)

        bind.execute(
            sa.text(
                f"UPDATE {table_name} "
                "SET created_by = COALESCE(created_by, usuario_auditoria), "
                "updated_by = COALESCE(updated_by, usuario_auditoria)"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    for table_name in reversed(TABLES):
        inspector = sa.inspect(bind)
        indexes = {index["name"] for index in inspector.get_indexes(table_name)}
        for column_name in reversed(AUDIT_COLUMNS):
            index_name = f"ix_{table_name}_{column_name}"
            if index_name in indexes:
                op.drop_index(index_name, table_name=table_name)

        columns = {column["name"] for column in sa.inspect(bind).get_columns(table_name)}
        for column_name in reversed(AUDIT_COLUMNS):
            if column_name in columns:
                op.drop_column(table_name, column_name)