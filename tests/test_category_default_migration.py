from __future__ import annotations

import importlib.util
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "src/osiris/db/alembic/versions/b84c1d6e2f90_add_category_default_marker.py"
)
SPEC = importlib.util.spec_from_file_location("category_default_migration", MIGRATION_PATH)
assert SPEC and SPEC.loader
MIGRATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATION)


def _run(engine, operation):
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            operation()


def test_migration_does_not_mark_legacy_general_by_name_and_is_reversible(capsys):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    categories = sa.Table(
        "tbl_categoria",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("parent_id", sa.Uuid()),
        sa.Column("es_padre", sa.Boolean(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
    )
    product_categories = sa.Table(
        "tbl_producto_categoria",
        metadata,
        sa.Column("producto_id", sa.Uuid(), nullable=False),
        sa.Column("categoria_id", sa.Uuid(), nullable=False),
    )
    metadata.create_all(engine)

    parent_id, general_id = uuid4(), uuid4()
    with engine.begin() as connection:
        connection.execute(
            categories.insert(),
            [
                {
                    "id": parent_id,
                    "nombre": "Computadoras",
                    "parent_id": None,
                    "es_padre": True,
                    "activo": True,
                },
                {
                    "id": general_id,
                    "nombre": "General",
                    "parent_id": parent_id,
                    "es_padre": False,
                    "activo": True,
                },
            ],
        )
        connection.execute(
            product_categories.insert().values(producto_id=uuid4(), categoria_id=general_id)
        )

    _run(engine, MIGRATION.upgrade)

    category_table = sa.table(
        "tbl_categoria",
        sa.column("id", sa.Uuid()),
        sa.column("is_default", sa.Boolean()),
    )
    with engine.connect() as connection:
        is_default = connection.execute(
            sa.select(category_table.c.is_default).where(category_table.c.id == general_id)
        ).scalar_one()
    assert is_default is False
    assert "no origin marker" in capsys.readouterr().out

    _run(engine, MIGRATION.downgrade)
    columns = {column["name"] for column in sa.inspect(engine).get_columns("tbl_categoria")}
    assert "is_default" not in columns
