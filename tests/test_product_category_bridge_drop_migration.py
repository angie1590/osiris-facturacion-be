from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


MIGRATION_FILE = (
    Path(__file__).parents[1]
    / "src/osiris/db/alembic/versions/f6a2c9d1e740_drop_product_category_bridge.py"
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
    sa.Table("tbl_categoria", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    sa.Table(
        "tbl_producto",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("categoria_principal_id", sa.Uuid()),
    )
    sa.Table(
        "tbl_producto_categoria",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("producto_id", sa.Uuid(), nullable=False),
        sa.Column("categoria_id", sa.Uuid(), nullable=False),
    )
    metadata.create_all(engine)
    return engine


def test_bridge_drop_requires_fk_projection_to_match_and_restores_from_fk_on_downgrade():
    engine = _engine()
    product_id, category_id = uuid4(), uuid4()
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO tbl_producto (id, activo, categoria_principal_id) "
                    "VALUES (:id, true, :category_id)"
                ),
                {"id": str(product_id), "category_id": str(category_id)},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO tbl_producto_categoria (id, producto_id, categoria_id) "
                    "VALUES (:id, :product_id, :category_id)"
                ),
                {
                    "id": str(uuid4()),
                    "product_id": str(product_id),
                    "category_id": str(category_id),
                },
            )
            _run(connection, "upgrade")

        assert "tbl_producto_categoria" not in sa.inspect(engine).get_table_names()
        with engine.begin() as connection:
            _run(connection, "downgrade")
            restored = connection.execute(
                sa.text(
                    "SELECT producto_id, categoria_id FROM tbl_producto_categoria"
                )
            ).one()
        assert restored == (str(product_id), str(category_id))
        indexes = sa.inspect(engine).get_indexes("tbl_producto_categoria")
        assert any(
            index["name"] == "uq_tbl_producto_categoria_producto"
            and bool(index["unique"])
            for index in indexes
        )
    finally:
        engine.dispose()


def test_bridge_drop_refuses_fk_divergence_without_dropping_data():
    engine = _engine()
    product_id = uuid4()
    primary_category_id, bridge_category_id = uuid4(), uuid4()
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO tbl_producto (id, activo, categoria_principal_id) "
                    "VALUES (:id, true, :category_id)"
                ),
                {"id": str(product_id), "category_id": str(primary_category_id)},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO tbl_producto_categoria (id, producto_id, categoria_id) "
                    "VALUES (:id, :product_id, :category_id)"
                ),
                {
                    "id": str(uuid4()),
                    "product_id": str(product_id),
                    "category_id": str(bridge_category_id),
                },
            )
            with pytest.raises(RuntimeError, match="matching primary-category projection"):
                _run(connection, "upgrade")

        assert "tbl_producto_categoria" in sa.inspect(engine).get_table_names()
        with engine.connect() as connection:
            relation = connection.execute(
                sa.text(
                    "SELECT categoria_id FROM tbl_producto_categoria WHERE producto_id = :id"
                ),
                {"id": str(product_id)},
            ).scalar_one()
        assert relation == str(bridge_category_id)
    finally:
        engine.dispose()