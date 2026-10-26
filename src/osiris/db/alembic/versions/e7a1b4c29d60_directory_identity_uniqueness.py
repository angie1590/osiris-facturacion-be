"""Protect global directory identity and role uniqueness.

Revision ID: e7a1b4c29d60
Revises: d6f9a3c18b50
"""

from __future__ import annotations

from typing import Any
import sqlalchemy as sa
from alembic import op

revision = "e7a1b4c29d60"
down_revision = "d6f9a3c18b50"
branch_labels = None
depends_on = None

INDEXES = (
    (
        "tbl_proveedor_persona",
        "persona_id",
        "ix_tbl_proveedor_persona_persona_id",
        "persona_id",
    ),
    (
        "tbl_usuario",
        "username",
        "uq_tbl_usuario_username_normalizado",
        "lower(trim(username))",
    ),
    (
        "tbl_tipo_cliente",
        "nombre",
        "uq_tbl_tipo_cliente_nombre_normalizado",
        "lower(trim(nombre))",
    ),
    (
        "tbl_persona",
        "identificacion",
        "uq_tbl_persona_identificacion_normalizada",
        "upper(trim(identificacion))",
    ),
)


def upgrade() -> None:
    connection = op.get_bind()
    for table_name, field, _, expression in INDEXES:
        table = sa.table(table_name, sa.column(field))
        key: Any = sa.literal_column(expression)
        duplicate = connection.execute(
            sa.select(key)
            .select_from(table)
            .group_by(key)
            .having(sa.func.count() > 1)
            .limit(1)
        ).first()
        if duplicate is not None:
            raise RuntimeError(
                f"Directorio contiene duplicados normalizados en {table_name}.{field}; "
                "ejecutar scripts/audit_directory_integrity.py y resolver "
                "las referencias con aprobacion administrativa antes de migrar."
            )
    for table_name, _, index_name, expression in INDEXES:
        op.create_index(index_name, table_name, [sa.text(expression)], unique=True)


def downgrade() -> None:
    for table_name, _, index_name, _ in reversed(INDEXES):
        op.drop_index(index_name, table_name=table_name)
