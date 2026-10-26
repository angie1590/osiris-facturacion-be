from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "src/osiris/db/alembic/versions/d4a8c2f19e63_unique_active_attribute_names.py"
)
SPEC = importlib.util.spec_from_file_location("attribute_name_unique_migration", MIGRATION_PATH)
assert SPEC and SPEC.loader
MIGRATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATION)


def _database():
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    attributes = sa.Table(
        "tbl_atributo",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
    )
    metadata.create_all(engine)
    return engine, attributes


def _run(engine, operation):
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            operation()


def test_migration_reports_existing_active_duplicate_names():
    engine, attributes = _database()
    with engine.begin() as connection:
        connection.execute(
            attributes.insert(),
            [
                {"nombre": "DPI", "activo": True},
                {"nombre": " dpi ", "activo": True},
            ],
        )

    with pytest.raises(RuntimeError, match=r"deactivate or rename duplicates first: dpi \(2\)"):
        _run(engine, MIGRATION.upgrade)


def test_migration_enforces_normalized_names_only_for_active_attributes():
    engine, attributes = _database()
    with engine.begin() as connection:
        connection.execute(attributes.insert().values(nombre="DPI", activo=True))
    _run(engine, MIGRATION.upgrade)

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(attributes.insert().values(nombre=" dpi ", activo=True))

    with engine.begin() as connection:
        connection.execute(attributes.insert().values(nombre="dpi", activo=False))

    _run(engine, MIGRATION.downgrade)