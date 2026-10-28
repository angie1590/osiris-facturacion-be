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
    / "src/osiris/db/alembic/versions/d3b9e8a1c6f4_require_category_for_active_product.py"
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
        "tbl_categoria",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
    )
    sa.Table(
        "tbl_producto",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("categoria_principal_id", sa.Uuid()),
    )
    metadata.create_all(engine)
    return engine


def test_active_product_requires_primary_category_but_inactive_history_is_allowed():
    engine = _engine()
    category_id = uuid4()
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text("INSERT INTO tbl_producto (id, activo, categoria_principal_id) VALUES (:id, false, NULL)"),
                {"id": str(uuid4())},
            )
            _run(connection, "upgrade")

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    sa.text("INSERT INTO tbl_producto (id, activo, categoria_principal_id) VALUES (:id, true, NULL)"),
                    {"id": str(uuid4())},
                )

        with engine.begin() as connection:
            connection.execute(
                sa.text("INSERT INTO tbl_producto (id, activo, categoria_principal_id) VALUES (:id, true, :category_id)"),
                {"id": str(uuid4()), "category_id": str(category_id)},
            )
            _run(connection, "downgrade")
            connection.execute(
                sa.text("INSERT INTO tbl_producto (id, activo, categoria_principal_id) VALUES (:id, true, NULL)"),
                {"id": str(uuid4())},
            )
    finally:
        engine.dispose()


def test_upgrade_refuses_existing_active_products_without_category():
    engine = _engine()
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text("INSERT INTO tbl_producto (id, activo, categoria_principal_id) VALUES (:id, true, NULL)"),
                {"id": str(uuid4())},
            )
            with pytest.raises(RuntimeError, match="active products without a primary category"):
                _run(connection, "upgrade")
    finally:
        engine.dispose()