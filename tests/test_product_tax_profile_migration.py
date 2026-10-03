from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "src/osiris/db/alembic/versions/a73f2c9d1e60_scope_product_taxes_by_company.py"
)
SPEC = importlib.util.spec_from_file_location("product_tax_profile_migration", MIGRATION_PATH)
assert SPEC and SPEC.loader
MIGRATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATION)


def _database(*, configured: bool):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    companies = sa.Table(
        "tbl_empresa",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("impuesto_catalogo_ids", sa.JSON(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
    )
    products = sa.Table(
        "tbl_producto",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tipo", sa.String(), nullable=False),
    )
    taxes = sa.Table(
        "aux_impuesto_catalogo",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tipo_impuesto", sa.String(), nullable=False),
        sa.Column("porcentaje_iva", sa.Numeric()),
        sa.Column("clasificacion_iva", sa.String()),
        sa.Column("aplica_a", sa.String(), nullable=False),
        sa.Column("vigente_desde", sa.Date(), nullable=False),
        sa.Column("vigente_hasta", sa.Date()),
        sa.Column("activo", sa.Boolean(), nullable=False),
    )
    warehouses = sa.Table(
        "tbl_bodega",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("empresa_id", sa.Uuid(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
    )
    product_warehouses = sa.Table(
        "tbl_producto_bodega",
        metadata,
        sa.Column("producto_id", sa.Uuid(), nullable=False),
        sa.Column("bodega_id", sa.Uuid(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
    )
    assignments = sa.Table(
        "tbl_producto_impuesto",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("producto_id", sa.Uuid(), nullable=False),
        sa.Column("impuesto_catalogo_id", sa.Uuid(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
    )
    metadata.create_all(engine)

    company_id, product_id, warehouse_id = uuid4(), uuid4(), uuid4()
    iva_zero_id, ice_id, assignment_id = uuid4(), uuid4(), uuid4()
    with engine.begin() as connection:
        connection.execute(
            companies.insert().values(
                id=company_id,
                impuesto_catalogo_ids=[str(ice_id)] if configured else [],
                activo=True,
            )
        )
        connection.execute(products.insert().values(id=product_id, tipo="BIEN"))
        connection.execute(
            taxes.insert(),
            [
                {
                    "id": iva_zero_id,
                    "tipo_impuesto": "IVA",
                    "porcentaje_iva": 0,
                    "clasificacion_iva": None,
                    "aplica_a": "AMBOS",
                    "vigente_desde": date(2020, 1, 1),
                    "vigente_hasta": None,
                    "activo": True,
                },
                {
                    "id": ice_id,
                    "tipo_impuesto": "ICE",
                    "porcentaje_iva": None,
                    "clasificacion_iva": None,
                    "aplica_a": "AMBOS",
                    "vigente_desde": date(2020, 1, 1),
                    "vigente_hasta": None,
                    "activo": True,
                },
            ],
        )
        connection.execute(
            warehouses.insert().values(id=warehouse_id, empresa_id=company_id, activo=True)
        )
        connection.execute(
            product_warehouses.insert().values(
                producto_id=product_id,
                bodega_id=warehouse_id,
                activo=True,
            )
        )
        connection.execute(
            assignments.insert().values(
                id=assignment_id,
                producto_id=product_id,
                impuesto_catalogo_id=ice_id,
                activo=True,
            )
        )
    return engine, company_id, iva_zero_id, assignment_id


def _run(engine, operation):
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            operation()


def test_upgrade_blocks_unconfigured_legacy_assignments_without_schema_changes():
    engine, _company_id, _iva_zero_id, assignment_id = _database(configured=False)

    with pytest.raises(RuntimeError, match=f"{assignment_id}.*not configured"):
        _run(engine, MIGRATION.upgrade)

    columns = {column["name"] for column in sa.inspect(engine).get_columns("tbl_producto_impuesto")}
    assert "empresa_id" not in columns
    with engine.connect() as connection:
        assert connection.execute(
            sa.text("SELECT impuesto_catalogo_ids FROM tbl_empresa")
        ).scalar_one() == "[]"


def test_upgrade_backfills_company_adds_default_iva_and_downgrades_on_sqlite():
    engine, company_id, iva_zero_id, assignment_id = _database(configured=True)

    _run(engine, MIGRATION.upgrade)

    assignment_table = sa.table(
        "tbl_producto_impuesto",
        sa.column("id", sa.Uuid()),
        sa.column("empresa_id", sa.Uuid()),
    )
    company_table = sa.table(
        "tbl_empresa",
        sa.column("id", sa.Uuid()),
        sa.column("impuesto_catalogo_ids", sa.JSON()),
    )
    with engine.connect() as connection:
        assignment = connection.execute(
            sa.select(assignment_table.c.empresa_id).where(
                assignment_table.c.id == assignment_id
            )
        ).scalar_one()
        configured_ids = connection.execute(
            sa.select(company_table.c.impuesto_catalogo_ids).where(
                company_table.c.id == company_id
            )
        ).scalar_one()

    assert assignment == company_id
    assert str(iva_zero_id) in configured_ids

    _run(engine, MIGRATION.downgrade)
    columns = {column["name"] for column in sa.inspect(engine).get_columns("tbl_producto_impuesto")}
    assert "empresa_id" not in columns