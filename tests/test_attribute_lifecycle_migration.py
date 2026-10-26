from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


MIGRATION_PATH = Path(__file__).parents[1] / "src/osiris/db/alembic/versions/c5e91a7d2b64_add_attribute_change_snapshots.py"
SPEC = importlib.util.spec_from_file_location("attribute_change_migration", MIGRATION_PATH)
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
        connection.execute(sa.Table("tbl_atributo", sa.MetaData(), autoload_with=connection).insert().values(id=attribute_id.hex))
    _run(engine, MIGRATION.upgrade)
    snapshots = sa.Table("tbl_atributo_cambio", sa.MetaData(), autoload_with=engine)
    snapshot_id = uuid4()
    with engine.begin() as connection:
        connection.execute(snapshots.insert().values(
            id=snapshot_id.hex, creado_en=datetime(2026, 1, 1), actualizado_en=datetime(2026, 1, 1),
            atributo_id=attribute_id.hex, operacion="update", definicion_anterior={}, definicion_posterior={},
            asignaciones_anteriores=[], asignaciones_posteriores=[], valores_anteriores=[], valores_posteriores=[],
            remapeos_anteriores=[], remapeos_posteriores=[], revertido=False,
        ))
    with pytest.raises(RuntimeError, match="unreverted attribute snapshots"):
        _run(engine, MIGRATION.downgrade)
    with engine.begin() as connection:
        connection.execute(snapshots.update().values(revertido=True))
        assert connection.execute(sa.select(sa.func.count()).select_from(sa.Table("tbl_atributo", sa.MetaData(), autoload_with=connection))).scalar_one() == 1
    _run(engine, MIGRATION.downgrade)
    assert "tbl_atributo_cambio" not in sa.inspect(engine).get_table_names()