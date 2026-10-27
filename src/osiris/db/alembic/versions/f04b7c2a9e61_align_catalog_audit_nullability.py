"""Align catalog audit actor nullability with the optional model contract.

Revision ID: f04b7c2a9e61
Revises: e2b7d3f0c851
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f04b7c2a9e61"
down_revision: Union[str, None] = "e2b7d3f0c851"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("tbl_atributo", "tbl_categoria", "tbl_categoria_atributo")


def _alter_nullability(table_name: str, nullable: bool) -> None:
    bind = op.get_bind()
    index_definitions: dict[str, str] = {}
    if bind.dialect.name == "sqlite":
        index_definitions = {
            row[0]: row[1]
            for row in bind.execute(
                sa.text(
                    "SELECT name, sql FROM sqlite_master "
                    "WHERE type = 'index' AND tbl_name = :table_name AND sql IS NOT NULL"
                ),
                {"table_name": table_name},
            ).all()
        }
    with op.batch_alter_table(table_name) as batch:
        batch.alter_column(
            "usuario_auditoria",
            existing_type=sa.String(length=255),
            nullable=nullable,
        )
    if index_definitions:
        existing = {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}
        for name, definition in index_definitions.items():
            if name not in existing:
                bind.exec_driver_sql(definition)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table_name in TABLES:
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if "usuario_auditoria" not in columns:
            raise RuntimeError(
                f"Cannot align audit nullability: {table_name}.usuario_auditoria is missing."
            )
        if not next(
            column["nullable"]
            for column in inspector.get_columns(table_name)
            if column["name"] == "usuario_auditoria"
        ):
            _alter_nullability(table_name, nullable=True)
        inspector = sa.inspect(bind)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    nullable_tables: list[str] = []
    for table_name in TABLES:
        column = next(
            column
            for column in inspector.get_columns(table_name)
            if column["name"] == "usuario_auditoria"
        )
        if column["nullable"]:
            nullable_tables.append(table_name)
    null_rows = {
        table_name: bind.execute(
            sa.text(f"SELECT count(*) FROM {table_name} WHERE usuario_auditoria IS NULL")
        ).scalar_one()
        for table_name in nullable_tables
    }
    blocked = {table_name: count for table_name, count in null_rows.items() if count}
    if blocked:
        raise RuntimeError(
            "Cannot restore NOT NULL audit actor columns while null values exist: "
            + ", ".join(f"{table}={count}" for table, count in sorted(blocked.items()))
        )
    for table_name in nullable_tables:
        _alter_nullability(table_name, nullable=False)