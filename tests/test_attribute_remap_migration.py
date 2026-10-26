from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "src/osiris/db/alembic/versions/d6f9a3c18b50_attribute_value_remap.py"
)
SPEC = importlib.util.spec_from_file_location(
    "attribute_remap_migration", MIGRATION_PATH
)
assert SPEC and SPEC.loader
MIGRATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATION)


AUDIT_MIGRATION_PATH = MIGRATION_PATH.with_name(
    "b0d4e7f52a93_attribute_remap_audit_columns.py"
)
AUDIT_SPEC = importlib.util.spec_from_file_location(
    "attribute_remap_audit_migration", AUDIT_MIGRATION_PATH
)
assert AUDIT_SPEC and AUDIT_SPEC.loader
AUDIT_MIGRATION = importlib.util.module_from_spec(AUDIT_SPEC)
AUDIT_SPEC.loader.exec_module(AUDIT_MIGRATION)


def _engine():
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("tbl_producto", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    sa.Table("tbl_atributo", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    metadata.create_all(engine)
    return engine


def _run(engine, operation):
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            operation()


def test_remap_table_migration_blocks_downgrade_until_pending_items_are_resolved():
    engine = _engine()
    _run(engine, MIGRATION.upgrade)

    product_id, attribute_id, remap_id = uuid4(), uuid4(), uuid4()
    remaps = sa.table(
        "tbl_producto_atributo_remapeo",
        sa.column("id", sa.Uuid()),
        sa.column("producto_id", sa.Uuid()),
        sa.column("atributo_id", sa.Uuid()),
        sa.column("tipo_anterior", sa.String()),
        sa.column("tipo_nuevo", sa.String()),
        sa.column("valor_anterior", sa.JSON()),
        sa.column("motivo", sa.String()),
        sa.column("activo", sa.Boolean()),
        sa.column("creado_en", sa.DateTime()),
        sa.column("actualizado_en", sa.DateTime()),
        sa.column("usuario_auditoria", sa.String()),
    )
    with engine.begin() as connection:
        connection.execute(
            sa.insert(remaps).values(
                id=remap_id,
                producto_id=product_id,
                atributo_id=attribute_id,
                tipo_anterior="string",
                tipo_nuevo="integer",
                valor_anterior={"value": "n/a"},
                motivo="invalid integer",
                activo=True,
                creado_en=datetime(2026, 1, 1),
                actualizado_en=datetime(2026, 1, 1),
                usuario_auditoria="test",
            )
        )

    with pytest.raises(RuntimeError, match="pending product attribute remaps"):
        _run(engine, MIGRATION.downgrade)

    with engine.begin() as connection:
        connection.execute(
            sa.update(remaps).where(remaps.c.id == remap_id).values(activo=False)
        )
    _run(engine, MIGRATION.downgrade)
    assert "tbl_producto_atributo_remapeo" not in sa.inspect(engine).get_table_names()


@pytest.mark.parametrize("active", [True, False])
def test_remap_audit_migration_preserves_rows_and_foreign_keys(active):
    engine = _engine()
    _run(engine, MIGRATION.upgrade)
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        metadata = sa.MetaData()
        products = sa.Table("tbl_producto", metadata, autoload_with=connection)
        attributes = sa.Table("tbl_atributo", metadata, autoload_with=connection)
        remaps = sa.Table(
            "tbl_producto_atributo_remapeo", metadata, autoload_with=connection
        )
        product_id, attribute_id, remap_id = uuid4().hex, uuid4().hex, uuid4().hex
        connection.execute(products.insert().values(id=product_id))
        connection.execute(attributes.insert().values(id=attribute_id))
        connection.execute(
            remaps.insert().values(
                id=remap_id,
                producto_id=product_id,
                atributo_id=attribute_id,
                tipo_anterior="string",
                tipo_nuevo="integer",
                valor_anterior={"value": "n/a"},
                motivo="invalid integer",
                activo=active,
                creado_en=datetime(2026, 1, 1),
                actualizado_en=datetime(2026, 1, 2),
                usuario_auditoria="legacy_actor",
            )
        )
        original = dict(connection.execute(sa.select(remaps)).mappings().one())

    original_foreign_keys = sorted(
        sa.inspect(engine).get_foreign_keys(remaps.name),
        key=lambda foreign_key: foreign_key["referred_table"],
    )
    original_indexes = sa.inspect(engine).get_indexes(remaps.name)
    _run(engine, AUDIT_MIGRATION.upgrade)
    columns = {
        column["name"]: column for column in sa.inspect(engine).get_columns(remaps.name)
    }
    assert columns["created_by"]["nullable"]
    assert columns["updated_by"]["nullable"]
    assert columns["created_by"]["type"].length == 255
    assert columns["updated_by"]["type"].length == 255
    indexes = {index["name"] for index in sa.inspect(engine).get_indexes(remaps.name)}
    assert {f"ix_{remaps.name}_created_by", f"ix_{remaps.name}_updated_by"} <= indexes
    assert (
        sorted(
            sa.inspect(engine).get_foreign_keys(remaps.name),
            key=lambda foreign_key: foreign_key["referred_table"],
        )
        == original_foreign_keys
    )
    with engine.begin() as connection:
        upgraded = sa.Table(remaps.name, sa.MetaData(), autoload_with=connection)
        row = dict(connection.execute(sa.select(upgraded)).mappings().one())
        assert row.pop("created_by") == "legacy_actor"
        assert row.pop("updated_by") == "legacy_actor"
        assert row == original
        connection.execute(
            upgraded.update().values(created_by="creator", updated_by="editor")
        )
        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(products.delete())

    _run(engine, AUDIT_MIGRATION.downgrade)
    assert {
        column["name"] for column in sa.inspect(engine).get_columns(remaps.name)
    } == set(original)
    assert (
        sorted(
            sa.inspect(engine).get_foreign_keys(remaps.name),
            key=lambda foreign_key: foreign_key["referred_table"],
        )
        == original_foreign_keys
    )
    assert sa.inspect(engine).get_indexes(remaps.name) == original_indexes
    with engine.connect() as connection:
        assert dict(connection.execute(sa.select(remaps)).mappings().one()) == original
    _run(engine, AUDIT_MIGRATION.upgrade)
    with engine.connect() as connection:
        upgraded = sa.Table(remaps.name, sa.MetaData(), autoload_with=connection)
        assert (
            connection.execute(sa.select(upgraded.c.created_by)).scalar_one()
            == "legacy_actor"
        )
