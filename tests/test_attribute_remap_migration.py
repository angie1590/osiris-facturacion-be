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
SPEC = importlib.util.spec_from_file_location("attribute_remap_migration", MIGRATION_PATH)
assert SPEC and SPEC.loader
MIGRATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATION)


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
        connection.execute(sa.update(remaps).where(remaps.c.id == remap_id).values(activo=False))
    _run(engine, MIGRATION.downgrade)
    assert "tbl_producto_atributo_remapeo" not in sa.inspect(engine).get_table_names()
