from __future__ import annotations

import importlib.util
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "src/osiris/db/alembic/versions/c5e91a7d2b64_add_attribute_change_snapshots.py"
)
SPEC = importlib.util.spec_from_file_location(
    "attribute_change_migration", MIGRATION_PATH
)
assert SPEC and SPEC.loader
MIGRATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATION)


def _engine():
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("tbl_atributo", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    metadata.create_all(engine)
    return engine


def _run(engine, operation):
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            operation()


def test_snapshot_migration_is_non_destructive_and_downgrade_guards_recovery():
    engine = _engine()
    attribute_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            sa.Table("tbl_atributo", sa.MetaData(), autoload_with=connection)
            .insert()
            .values(id=attribute_id.hex)
        )
    _run(engine, MIGRATION.upgrade)
    snapshots = sa.Table("tbl_atributo_cambio", sa.MetaData(), autoload_with=engine)
    snapshot_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            snapshots.insert().values(
                id=snapshot_id.hex,
                creado_en=datetime(2026, 1, 1),
                actualizado_en=datetime(2026, 1, 1),
                atributo_id=attribute_id.hex,
                operacion="update",
                definicion_anterior={},
                definicion_posterior={},
                asignaciones_anteriores=[],
                asignaciones_posteriores=[],
                valores_anteriores=[],
                valores_posteriores=[],
                remapeos_anteriores=[],
                remapeos_posteriores=[],
                revertido=False,
            )
        )
    with pytest.raises(RuntimeError, match="unreverted attribute snapshots"):
        _run(engine, MIGRATION.downgrade)
    with engine.begin() as connection:
        connection.execute(snapshots.update().values(revertido=True))
        assert (
            connection.execute(
                sa.select(sa.func.count()).select_from(
                    sa.Table("tbl_atributo", sa.MetaData(), autoload_with=connection)
                )
            ).scalar_one()
            == 1
        )
    _run(engine, MIGRATION.downgrade)
    assert "tbl_atributo_cambio" not in sa.inspect(engine).get_table_names()


def test_snapshot_migration_postgresql_isolated_schema():
    value = os.environ.get("CATALOG_TEST_DATABASE_URL")
    if not value:
        pytest.skip("PostgreSQL opt-in: CATALOG_TEST_DATABASE_URL is not configured")
    url = sa.engine.make_url(value)
    if url.get_backend_name() != "postgresql":
        pytest.fail("CATALOG_TEST_DATABASE_URL must point to PostgreSQL")

    admin = sa.create_engine(
        url.set(drivername="postgresql+psycopg"),
        hide_parameters=True,
        connect_args={"connect_timeout": 5},
    )
    schema = "attribute_snapshot_test_" + uuid4().hex
    with admin.begin() as connection:
        connection.execute(sa.schema.CreateSchema(schema))
    engine = sa.create_engine(
        admin.url,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 5,
            "options": f"-c search_path={schema},pg_catalog -c lock_timeout=3000",
        },
    )
    attribute_id = uuid4()
    snapshot_id = uuid4()
    try:
        attributes = sa.Table(
            "tbl_atributo",
            sa.MetaData(),
            sa.Column("id", sa.Uuid(), primary_key=True),
        )
        attributes.create(engine)
        with engine.begin() as connection:
            connection.execute(attributes.insert().values(id=attribute_id))

        _run(engine, MIGRATION.upgrade)
        snapshots = sa.Table(
            "tbl_atributo_cambio", sa.MetaData(), autoload_with=engine
        )
        with engine.begin() as connection:
            connection.execute(
                snapshots.insert().values(
                    id=snapshot_id,
                    creado_en=datetime(2026, 1, 1),
                    actualizado_en=datetime(2026, 1, 1),
                    atributo_id=attribute_id,
                    operacion="update",
                    definicion_anterior={},
                    definicion_posterior={},
                    asignaciones_anteriores=[],
                    asignaciones_posteriores=[],
                    valores_anteriores=[],
                    valores_posteriores=[],
                    remapeos_anteriores=[],
                    remapeos_posteriores=[],
                    revertido=False,
                )
            )

        with pytest.raises(RuntimeError, match="unreverted attribute snapshots"):
            _run(engine, MIGRATION.downgrade)
        with engine.begin() as connection:
            assert connection.execute(
                sa.select(sa.func.count()).select_from(snapshots)
            ).scalar_one() == 1
            assert connection.execute(
                sa.select(sa.func.count()).select_from(attributes)
            ).scalar_one() == 1
            connection.execute(
                snapshots.update().values(revertido=True)
            )

        _run(engine, MIGRATION.downgrade)
        assert "tbl_atributo_cambio" not in sa.inspect(engine).get_table_names()
        with engine.connect() as connection:
            assert connection.execute(
                sa.select(sa.func.count()).select_from(attributes)
            ).scalar_one() == 1
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(sa.schema.DropSchema(schema, cascade=True))
        admin.dispose()
