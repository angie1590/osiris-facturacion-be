from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


VERSIONS_DIR = Path(__file__).parents[1] / "src/osiris/db/alembic/versions"


def _load_migration(filename: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, VERSIONS_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_migration(engine, migration, operation: str) -> None:
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            getattr(migration, operation)()


def test_taxpayer_seed_is_parameterized_and_idempotent_on_sqlite():
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table(
        "aux_tipo_contribuyente",
        metadata,
        sa.Column("codigo", sa.String(10), primary_key=True),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("descripcion", sa.String(255), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
    )
    metadata.create_all(engine)
    migration = _load_migration(
        "483805449635_seed_tipo_contribuyente.py",
        "seed_taxpayer_migration",
    )

    _run_migration(engine, migration, "upgrade")
    _run_migration(engine, migration, "upgrade")

    with engine.connect() as connection:
        rows = connection.execute(
            sa.text("SELECT codigo, descripcion FROM aux_tipo_contribuyente ORDER BY codigo")
        ).all()
    assert len(rows) == 5
    assert rows[0].codigo == "01"
    assert rows[2].descripcion == "Persona natural con ingresos anuales hasta $20,000."

    _run_migration(engine, migration, "downgrade")
    with engine.connect() as connection:
        assert connection.execute(
            sa.text("SELECT count(*) FROM aux_tipo_contribuyente")
        ).scalar_one() == 0


def test_duplicate_employee_photo_revision_is_safe_and_keeps_predecessor_column():
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table(
        "tbl_empleado",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("foto", sa.String(), nullable=True),
    )
    metadata.create_all(engine)
    migration = _load_migration(
        "d830a262e67a_add_empleado_foto_column.py",
        "duplicate_employee_photo_migration",
    )

    _run_migration(engine, migration, "upgrade")
    _run_migration(engine, migration, "downgrade")

    columns = {column["name"] for column in sa.inspect(engine).get_columns("tbl_empleado")}
    assert "foto" in columns
