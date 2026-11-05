from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError


MIGRATION_FILE = (
    Path(__file__).parents[1]
    / "src/osiris/db/alembic/versions/e1f4a8d63c20_unique_product_category_bridge.py"
)


def _migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location(MIGRATION_FILE.stem, MIGRATION_FILE)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _run(connection: sa.Connection, operation: str) -> None:
    migration = _migration()
    with Operations.context(MigrationContext.configure(connection)):
        getattr(migration, operation)()


def _engine() -> sa.Engine:
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table(
        "tbl_producto_categoria",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("producto_id", sa.Uuid(), nullable=False),
        sa.Column("categoria_id", sa.Uuid(), nullable=False),
    )
    metadata.create_all(engine)
    return engine


def test_bridge_unique_index_prevents_multiple_categories_and_downgrades():
    engine = _engine()
    product_id = uuid4()
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO tbl_producto_categoria (id, producto_id, categoria_id) "
                    "VALUES (:id, :product_id, :category_id)"
                ),
                {"id": str(uuid4()), "product_id": str(product_id), "category_id": str(uuid4())},
            )
            _run(connection, "upgrade")

        index = next(
            item
            for item in sa.inspect(engine).get_indexes("tbl_producto_categoria")
            if item["name"] == "uq_tbl_producto_categoria_producto"
        )
        assert bool(index["unique"])

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    sa.text(
                        "INSERT INTO tbl_producto_categoria (id, producto_id, categoria_id) "
                        "VALUES (:id, :product_id, :category_id)"
                    ),
                    {"id": str(uuid4()), "product_id": str(product_id), "category_id": str(uuid4())},
                )

        with engine.begin() as connection:
            _run(connection, "downgrade")
            connection.execute(
                sa.text(
                    "INSERT INTO tbl_producto_categoria (id, producto_id, categoria_id) "
                    "VALUES (:id, :product_id, :category_id)"
                ),
                {"id": str(uuid4()), "product_id": str(product_id), "category_id": str(uuid4())},
            )
    finally:
        engine.dispose()


def test_bridge_unique_migration_refuses_existing_duplicates_without_mutation():
    engine = _engine()
    product_id = uuid4()
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO tbl_producto_categoria (id, producto_id, categoria_id) "
                    "VALUES (:id, :product_id, :category_id)"
                ),
                [
                    {"id": str(uuid4()), "product_id": str(product_id), "category_id": str(uuid4())},
                    {"id": str(uuid4()), "product_id": str(product_id), "category_id": str(uuid4())},
                ],
            )
            with pytest.raises(RuntimeError, match="resolve duplicate bridge rows"):
                _run(connection, "upgrade")

        assert not any(
            index["name"] == "uq_tbl_producto_categoria_producto"
            for index in sa.inspect(engine).get_indexes("tbl_producto_categoria")
        )
        with engine.begin() as connection:
            count = connection.scalar(
                sa.text(
                    "SELECT count(*) FROM tbl_producto_categoria WHERE producto_id = :product_id"
                ),
                {"product_id": str(product_id)},
            )
        assert count == 2
    finally:
        engine.dispose()