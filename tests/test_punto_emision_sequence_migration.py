from __future__ import annotations

import importlib.util
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "src"
    / "osiris"
    / "db"
    / "alembic"
    / "versions"
    / "f61a8d3c2b90_enforce_punto_emision_sequences.py"
)


def _migration_module():
    spec = importlib.util.spec_from_file_location("punto_sequence_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sequence_migration_backfills_modality_and_legacy_counter_on_sqlite():
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    empresa = sa.Table(
        "tbl_empresa",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("modo_emision", sa.String(40), nullable=False),
    )
    sucursal = sa.Table(
        "tbl_sucursal",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("empresa_id", sa.Uuid(), nullable=False),
    )
    sa.Table(
        "tbl_punto_emision",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("sucursal_id", sa.Uuid(), nullable=False),
        sa.Column("secuencial_actual", sa.Integer(), nullable=False, server_default="1"),
    )
    sa.Table(
        "tbl_punto_emision_secuencial",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("punto_emision_id", sa.Uuid(), nullable=False),
        sa.Column("tipo_documento", sa.String(40), nullable=False),
        sa.Column("secuencial_actual", sa.Integer(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False),
        sa.Column("usuario_auditoria", sa.String(255)),
        sa.Column("activo", sa.Boolean(), nullable=False),
    )
    venta = sa.Table(
        "tbl_venta",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("empresa_id", sa.Uuid()),
        sa.Column("punto_emision_id", sa.Uuid()),
        sa.Column("secuencial_formateado", sa.String(20)),
    )
    metadata.create_all(engine)

    company_id, branch_id, point_id = uuid4(), uuid4(), uuid4()
    with engine.begin() as connection:
        connection.execute(empresa.insert().values(id=company_id, modo_emision="NOTA_VENTA_FISICA"))
        connection.execute(sucursal.insert().values(id=branch_id, empresa_id=company_id))
        connection.execute(
            sa.table(
                "tbl_punto_emision",
                sa.column("id", sa.Uuid()),
                sa.column("sucursal_id", sa.Uuid()),
                sa.column("secuencial_actual", sa.Integer()),
            ).insert().values(id=point_id, sucursal_id=branch_id, secuencial_actual=1)
        )
        connection.execute(
            venta.insert(),
            [
                {"id": uuid4(), "empresa_id": company_id, "punto_emision_id": point_id, "secuencial_formateado": "001-001-000000004"},
                {"id": uuid4(), "empresa_id": company_id, "punto_emision_id": point_id, "secuencial_formateado": "001-001-000000007"},
            ],
        )

    migration = _migration_module()
    with engine.begin() as connection:
        operations = MigrationContext.configure(connection)
        with Operations.context(operations):
            migration.upgrade()

        migrated_point = sa.Table("tbl_punto_emision", sa.MetaData(), autoload_with=connection)
        migrated_counter = sa.Table(
            "tbl_punto_emision_secuencial", sa.MetaData(), autoload_with=connection
        )
        modality = connection.execute(
            sa.select(migrated_point.c.modalidad_emision).where(migrated_point.c.id == point_id)
        ).scalar_one()
        counter = connection.execute(
            sa.select(migrated_counter.c.secuencial_actual).where(
                migrated_counter.c.punto_emision_id == point_id,
                migrated_counter.c.tipo_documento == "FACTURA",
            )
        ).scalar_one()
        assert modality == "FISICA"
        assert counter == 7
        assert any(
            index["name"] == "uq_venta_empresa_punto_secuencial"
            for index in sa.inspect(connection).get_indexes("tbl_venta")
        )
        with pytest.raises(sa.exc.IntegrityError):
            with connection.begin_nested():
                connection.execute(
                    venta.insert().values(
                        id=uuid4(),
                        empresa_id=company_id,
                        punto_emision_id=point_id,
                        secuencial_formateado="001-001-000000007",
                    )
                )

        with Operations.context(operations):
            migration.downgrade()
        assert "modalidad_emision" not in {
            column["name"] for column in sa.inspect(connection).get_columns("tbl_punto_emision")
        }
