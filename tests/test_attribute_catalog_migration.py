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
    / "src/osiris/db/alembic/versions/c5e8b2a64d31_attribute_catalog_select.py"
)
SPEC = importlib.util.spec_from_file_location("attribute_catalog_migration", MIGRATION_PATH)
assert SPEC and SPEC.loader
MIGRATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATION)


def _database(*, duplicate_mapping: bool = False):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    attributes = sa.Table(
        "tbl_atributo",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False),
        sa.Column("usuario_auditoria", sa.String(), nullable=False),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("tipo_dato", sa.String(20), nullable=False),
    )
    mappings = sa.Table(
        "tbl_categoria_atributo",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("categoria_id", sa.Uuid(), nullable=False),
        sa.Column("atributo_id", sa.Uuid(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            sa.text("CREATE UNIQUE INDEX ix_tbl_atributo_nombre ON tbl_atributo (nombre)")
        )
        attribute_id, category_id = uuid4(), uuid4()
        connection.execute(
            attributes.insert().values(
                id=attribute_id,
                activo=True,
                creado_en=datetime(2026, 1, 1),
                actualizado_en=datetime(2026, 1, 1),
                usuario_auditoria="test",
                nombre="Color",
                tipo_dato="STRING",
            )
        )
        connection.execute(
            mappings.insert(),
            [
                {
                    "id": uuid4(),
                    "categoria_id": category_id,
                    "atributo_id": attribute_id,
                    "activo": True,
                }
                for _ in range(2 if duplicate_mapping else 1)
            ],
        )
    return engine


def _run(engine, operation):
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            operation()


def test_migration_refuses_duplicate_active_category_attribute_mappings_without_changes():
    engine = _database(duplicate_mapping=True)

    with pytest.raises(RuntimeError, match="duplicate mappings"):
        _run(engine, MIGRATION.upgrade)

    assert "tbl_catalogo" not in sa.inspect(engine).get_table_names()
    columns = {column["name"] for column in sa.inspect(engine).get_columns("tbl_atributo")}
    assert "catalog_id" not in columns


def test_migration_adds_catalog_attribute_fields_and_supports_safe_downgrade():
    engine = _database()

    _run(engine, MIGRATION.upgrade)

    columns = {column["name"] for column in sa.inspect(engine).get_columns("tbl_atributo")}
    assert {"select_options", "catalog_id", "allow_negative", "min_value", "max_value"} <= columns
    assert "ix_tbl_atributo_nombre" not in {index["name"] for index in sa.inspect(engine).get_indexes("tbl_atributo")}

    with engine.begin() as connection:
        connection.execute(sa.text("UPDATE tbl_atributo SET tipo_dato = 'SELECT'"))
    with pytest.raises(RuntimeError, match="SELECT or CATALOG"):
        _run(engine, MIGRATION.downgrade)

    with engine.begin() as connection:
        connection.execute(sa.text("UPDATE tbl_atributo SET tipo_dato = 'STRING'"))
    _run(engine, MIGRATION.downgrade)

    assert "tbl_catalogo" not in sa.inspect(engine).get_table_names()
    assert "ix_tbl_atributo_nombre" in {index["name"] for index in sa.inspect(engine).get_indexes("tbl_atributo")}
