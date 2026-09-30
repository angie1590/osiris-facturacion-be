from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "src"
    / "osiris"
    / "db"
    / "alembic"
    / "versions"
    / "c9d3e6a1b742_add_temporary_tax_measures.py"
)


def _migration_module():
    spec = importlib.util.spec_from_file_location("temporary_tax_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_upgrade_and_downgrade_on_sqlite():
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("tbl_empresa", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    sa.Table("tbl_producto", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    sa.Table("tbl_venta", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    sa.Table(
        "tbl_venta_detalle_impuesto",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tipo_impuesto", sa.String(10), nullable=False),
        sa.Column("tarifa", sa.Numeric(7, 4), nullable=False),
        sa.Column("base_imponible", sa.Numeric(12, 2), nullable=False),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO tbl_venta_detalle_impuesto (id, tipo_impuesto, tarifa, base_imponible) "
                "VALUES ('00000000-0000-0000-0000-000000000001', 'IVA', 15.0, 100.0), "
                "('00000000-0000-0000-0000-000000000002', 'ICE', 5.0, 100.0)"
            )
        )

    migration = _migration_module()
    with engine.begin() as connection:
        operations = MigrationContext.configure(connection)
        with Operations.context(operations):
            migration.upgrade()
        inspector = sa.inspect(connection)
        assert {"tbl_medida_tributaria_temporal", "tbl_medida_tributaria_producto"}.issubset(
            set(inspector.get_table_names())
        )
        sale_tax_columns = {column["name"] for column in inspector.get_columns("tbl_venta_detalle_impuesto")}
        assert {"componente", "unidad_gravable", "cantidad_gravable", "medida_temporal_id", "referencia_legal_temporal"}.issubset(sale_tax_columns)
        assert "subtotal_8" in {column["name"] for column in inspector.get_columns("tbl_venta")}
        assert inspector.get_foreign_keys("tbl_venta_detalle_impuesto")
        historic = connection.execute(
                sa.text(
                    "SELECT tarifa, base_imponible, componente, medida_temporal_id "
                    "FROM tbl_venta_detalle_impuesto WHERE tipo_impuesto = 'IVA'"
                )
        ).one()
        assert historic.tarifa == 15
        assert historic.base_imponible == 100
        assert historic.componente == "PORCENTUAL"
        assert historic.medida_temporal_id is None
        historic_ice = connection.execute(
            sa.text("SELECT tarifa, base_imponible, componente FROM tbl_venta_detalle_impuesto WHERE tipo_impuesto = 'ICE'")
        ).one()
        assert historic_ice.tarifa == 5
        assert historic_ice.base_imponible == 100
        assert historic_ice.componente == "AD_VALOREM"

        with Operations.context(operations):
            migration.downgrade()
        inspector = sa.inspect(connection)
        assert "tbl_medida_tributaria_temporal" not in inspector.get_table_names()
        assert "subtotal_8" not in {column["name"] for column in inspector.get_columns("tbl_venta")}
        assert {"id", "tipo_impuesto", "tarifa", "base_imponible"} == {
            column["name"] for column in inspector.get_columns("tbl_venta_detalle_impuesto")
        }
