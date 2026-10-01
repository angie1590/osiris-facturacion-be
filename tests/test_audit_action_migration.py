from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "src"
    / "osiris"
    / "db"
    / "alembic"
    / "versions"
    / "e3b91a7d5c20_expand_audit_action_length.py"
)


def _migration_module():
    spec = importlib.util.spec_from_file_location("audit_action_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_expand_audit_action_length_and_guard_downgrade():
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table(
        "audit_log",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("accion", sa.String(20), nullable=False),
    )
    metadata.create_all(engine)
    migration = _migration_module()

    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO audit_log (id, accion) "
                "VALUES ('00000000-0000-0000-0000-000000000001', 'UPDATE')"
            )
        )
        operations = MigrationContext.configure(connection)
        with Operations.context(operations):
            migration.upgrade()
        column = next(column for column in sa.inspect(connection).get_columns("audit_log") if column["name"] == "accion")
        assert column["type"].length == 64
        connection.execute(
            sa.text(
                "INSERT INTO audit_log (id, accion) "
                "VALUES ('00000000-0000-0000-0000-000000000002', 'UPDATE_EMPRESA_TRIBUTARIA')"
            )
        )
        with Operations.context(operations), pytest.raises(RuntimeError, match="actions longer than 20"):
            migration.downgrade()

        connection.execute(sa.text("DELETE FROM audit_log WHERE length(accion) > 20"))
        with Operations.context(operations):
            migration.downgrade()
        column = next(column for column in sa.inspect(connection).get_columns("audit_log") if column["name"] == "accion")
        assert column["type"].length == 20
