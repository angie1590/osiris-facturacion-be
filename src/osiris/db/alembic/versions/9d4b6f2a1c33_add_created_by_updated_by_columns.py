"""add created_by updated_by columns

Revision ID: 9d4b6f2a1c33
Revises: 7a1c9d4e2f10
Create Date: 2026-02-19 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9d4b6f2a1c33"
down_revision: Union[str, None] = "7a1c9d4e2f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables_with_usuario_auditoria() -> list[str]:
    inspector = sa.inspect(op.get_bind())
    tables: list[str] = []
    for table_name in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if "usuario_auditoria" in columns:
            tables.append(table_name)
    return tables


def upgrade() -> None:
    for table_name in _tables_with_usuario_auditoria():
        inspector = sa.inspect(op.get_bind())
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        indexes = {index["name"] for index in inspector.get_indexes(table_name)}

        if "created_by" not in columns:
            op.add_column(table_name, sa.Column("created_by", sa.String(length=255), nullable=True))
        if "updated_by" not in columns:
            op.add_column(table_name, sa.Column("updated_by", sa.String(length=255), nullable=True))

        op.execute(
            sa.text(
                f'UPDATE "{table_name}" '
                "SET created_by = COALESCE(created_by, usuario_auditoria), "
                "updated_by = COALESCE(updated_by, usuario_auditoria)"
            )
        )

        idx_created = f"ix_{table_name}_created_by"
        idx_updated = f"ix_{table_name}_updated_by"
        if idx_created not in indexes:
            op.create_index(idx_created, table_name, ["created_by"], unique=False)
        if idx_updated not in indexes:
            op.create_index(idx_updated, table_name, ["updated_by"], unique=False)


def downgrade() -> None:
    for table_name in _tables_with_usuario_auditoria():
        inspector = sa.inspect(op.get_bind())
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        indexes = {index["name"] for index in inspector.get_indexes(table_name)}

        idx_created = f"ix_{table_name}_created_by"
        idx_updated = f"ix_{table_name}_updated_by"
        if idx_created in indexes:
            op.drop_index(idx_created, table_name=table_name)
        if idx_updated in indexes:
            op.drop_index(idx_updated, table_name=table_name)

        if "updated_by" in columns:
            op.drop_column(table_name, "updated_by")
        if "created_by" in columns:
            op.drop_column(table_name, "created_by")
