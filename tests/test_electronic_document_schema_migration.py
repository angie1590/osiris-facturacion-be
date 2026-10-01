from __future__ import annotations

import importlib.util
from pathlib import Path

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
    / "d7a4c91e2f60_align_electronic_document_schema.py"
)


def _migration_module():
    spec = importlib.util.spec_from_file_location("electronic_document_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_backfills_existing_documents_and_downgrade_restores_legacy_shape():
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("tbl_venta", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    sa.Table(
        "tbl_documento_electronico",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("venta_id", sa.Uuid(), nullable=False),
        sa.Column("clave_acceso", sa.String(49), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(255)),
        sa.Column("updated_by", sa.String(255)),
        sa.Column("usuario_auditoria", sa.String()),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "estado IN ('ENVIADO', 'AUTORIZADO', 'RECHAZADO')",
            name="ck_tbl_documento_electronico_estado",
        ),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO tbl_documento_electronico "
                "(id, venta_id, clave_acceso, estado, creado_en, actualizado_en, activo) "
                "VALUES ('00000000-0000-0000-0000-000000000001', "
                "'00000000-0000-0000-0000-000000000002', 'clave', 'AUTORIZADO', "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, true)"
            )
        )

    migration = _migration_module()
    with engine.begin() as connection:
        operations = MigrationContext.configure(connection)
        with Operations.context(operations):
            migration.upgrade()
        inspector = sa.inspect(connection)
        columns = {column["name"] for column in inspector.get_columns("tbl_documento_electronico")}
        assert {
            "tipo_documento",
            "referencia_id",
            "estado_sri",
            "mensajes_sri",
            "xml_autorizado",
            "intentos",
            "next_retry_at",
            "cantidad_impresiones",
        }.issubset(columns)
        row = connection.execute(
            sa.text(
                "SELECT tipo_documento, referencia_id, venta_id, estado_sri, intentos, cantidad_impresiones "
                "FROM tbl_documento_electronico"
            )
        ).one()
        assert row.tipo_documento == "FACTURA"
        assert row.referencia_id == row.venta_id
        assert row.estado_sri == "AUTORIZADO"
        assert row.intentos == 0
        assert row.cantidad_impresiones == 0

        connection.execute(
            sa.text(
                "INSERT INTO tbl_documento_electronico "
                "(id, tipo_documento, venta_id, clave_acceso, estado, estado_sri, creado_en, actualizado_en, activo) "
                "VALUES ('00000000-0000-0000-0000-000000000003', 'RETENCION', NULL, NULL, "
                "'EN_COLA', 'EN_COLA', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, true)"
            )
        )
        with Operations.context(operations), pytest.raises(RuntimeError, match="non-legacy documents"):
            migration.downgrade()
        connection.execute(
            sa.text("DELETE FROM tbl_documento_electronico WHERE tipo_documento = 'RETENCION'")
        )

        with Operations.context(operations):
            migration.downgrade()
        inspector = sa.inspect(connection)
        legacy_columns = {column["name"] for column in inspector.get_columns("tbl_documento_electronico")}
        assert legacy_columns == {
            "id",
            "venta_id",
            "clave_acceso",
            "estado",
            "creado_en",
            "actualizado_en",
            "created_by",
            "updated_by",
            "usuario_auditoria",
            "activo",
        }
