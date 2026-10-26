from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "src/osiris/db/alembic/versions/c6f9d3a1b285_catalog_audit_columns.py"
)
SPEC = importlib.util.spec_from_file_location("catalog_audit_migration", MIGRATION_PATH)
assert SPEC and SPEC.loader
MIGRATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATION)


def test_migration_adds_audit_columns_and_backfills_catalog_actors():
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    for table_name in MIGRATION.TABLES:
        sa.Table(
            table_name,
            metadata,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("usuario_auditoria", sa.String(255), nullable=False),
        )
    metadata.create_all(engine)

    with engine.begin() as connection:
        for table_name in MIGRATION.TABLES:
            connection.execute(
                sa.text(f"INSERT INTO {table_name} (id, usuario_auditoria) VALUES (1, 'legacy-user')")
            )
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            MIGRATION.upgrade()

    inspector = sa.inspect(engine)
    for table_name in MIGRATION.TABLES:
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        indexes = {index["name"] for index in inspector.get_indexes(table_name)}
        assert set(MIGRATION.AUDIT_COLUMNS) <= columns
        assert {f"ix_{table_name}_{column}" for column in MIGRATION.AUDIT_COLUMNS} <= indexes
        with engine.connect() as connection:
            row = connection.execute(sa.text(f"SELECT created_by, updated_by FROM {table_name}")).one()
        assert row == ("legacy-user", "legacy-user")