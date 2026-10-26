from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from osiris.utils.directory_preflight import (
    DIRECTORY_KEYS,
    audit_directory,
    require_clean_directory,
)


def _database():
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    for name, key in DIRECTORY_KEYS.items():
        columns = [
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("activo", sa.Boolean(), nullable=False),
            sa.Column(key, sa.String(), nullable=False),
        ]
        if name == "tbl_usuario":
            columns.append(sa.Column("persona_id", sa.String(), nullable=False))
        if name == "tbl_cliente":
            columns.append(sa.Column("tipo_cliente_id", sa.String()))
        if name == "tbl_proveedor_sociedad":
            columns.append(sa.Column("persona_contacto_id", sa.String()))
        sa.Table(name, metadata, *columns)
    sa.Table(
        "aux_tipo_contribuyente", metadata,
        sa.Column("codigo", sa.String(), primary_key=True),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
    )
    metadata.create_all(engine)
    return engine, metadata


def test_directory_preflight_clean_and_pending_normalization_are_readonly():
    engine, metadata = _database()
    with engine.begin() as connection:
        connection.execute(metadata.tables["tbl_persona"].insert(), {
            "id": str(uuid4()), "activo": True, "identificacion": " ab123 ",
        })
        report = audit_directory(connection)
        assert report["apto_para_migrar"] is True
        assert report["total_conflictos"] == 0
        assert len(report["requieren_normalizacion"]) == 1
        require_clean_directory(connection)
        assert connection.scalar(sa.select(metadata.tables["tbl_persona"].c.identificacion)) == " ab123 "


@pytest.mark.parametrize("table,key,values", [
    ("tbl_persona", "identificacion", ["ab123", " AB123 "]),
    ("tbl_cliente", "persona_id", ["persona", "persona"]),
    ("tbl_proveedor_persona", "persona_id", ["persona", "persona"]),
    ("tbl_empleado", "persona_id", ["persona", "persona"]),
    ("tbl_usuario", "username", ["Andrea", " andrea "]),
    ("tbl_usuario", "persona_id", ["persona", "persona"]),
    ("tbl_tipo_cliente", "nombre", ["Mayorista", " mayorista "]),
    ("tbl_proveedor_sociedad", "ruc", ["1790000000001", " 1790000000001 "]),
])
def test_directory_preflight_blocks_duplicates_including_inactive(table, key, values):
    engine, metadata = _database()
    with engine.begin() as connection:
        for index, value in enumerate(values):
            row = {"id": str(uuid4()), "activo": index == 0, key: value}
            if table == "tbl_usuario":
                row.setdefault("username", f"user{index}")
                row.setdefault("persona_id", str(uuid4()))
            connection.execute(metadata.tables[table].insert(), row)
        report = audit_directory(connection)
        assert report["apto_para_migrar"] is False
        assert report["total_conflictos"] == 1
        conflict = report["conflictos"][0]
        assert conflict["tabla"] == table
        assert conflict["campo"] == key
        assert {row["activo"] for row in conflict["registros"]} == {True, False}
        with pytest.raises(RuntimeError, match="duplicados normalizados"):
            require_clean_directory(connection)
        assert connection.scalar(sa.select(sa.func.count()).select_from(metadata.tables[table])) == 2


def test_directory_preflight_reports_contact_and_role_references():
    engine, metadata = _database()
    person_id = str(uuid4())
    with engine.begin() as connection:
        connection.execute(metadata.tables["tbl_persona"].insert(), [
            {"id": person_id, "activo": True, "identificacion": "AB123"},
            {"id": str(uuid4()), "activo": False, "identificacion": "ab123"},
        ])
        connection.execute(metadata.tables["tbl_cliente"].insert(), {
            "id": str(uuid4()), "activo": True, "persona_id": person_id,
        })
        connection.execute(metadata.tables["tbl_proveedor_sociedad"].insert(), {
            "id": str(uuid4()), "activo": False, "ruc": "1790000000001",
            "persona_contacto_id": person_id,
        })
        references = audit_directory(connection)["conflictos"][0]["referencias_directorio"]
        assert {reference["tabla"] for reference in references} == {
            "tbl_cliente", "tbl_proveedor_sociedad",
        }


def test_directory_preflight_reports_historical_foreign_keys_outside_directory():
    engine, metadata = _database()
    historical = sa.Table(
        "tbl_compra_historica", metadata,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("proveedor_id", sa.String(), sa.ForeignKey("tbl_proveedor_persona.id")),
        sa.Column("activo", sa.Boolean(), nullable=False),
    )
    historical.create(engine)
    supplier_id = str(uuid4())
    with engine.begin() as connection:
        connection.execute(metadata.tables["tbl_proveedor_persona"].insert(), [
            {"id": supplier_id, "activo": True, "persona_id": "persona"},
            {"id": str(uuid4()), "activo": False, "persona_id": "persona"},
        ])
        connection.execute(historical.insert(), {
            "id": str(uuid4()), "proveedor_id": supplier_id, "activo": False,
        })
        conflict = audit_directory(connection)["conflictos"][0]
        assert len(conflict["referencias_historicas"]) == 1
        assert conflict["referencias_historicas"][0]["tabla"] == "tbl_compra_historica"
        assert conflict["referencias_historicas"][0]["activo"] is False


def _migration(filename="e7a1b4c29d60_directory_identity_uniqueness.py"):
    path = Path(__file__).parents[1] / "src/osiris/db/alembic/versions" / filename
    spec = importlib.util.spec_from_file_location("directory_identity_migration", path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_taxpayer_applicability_backfill_and_downgrade():
    engine, metadata = _database()
    migration = _migration("f8b2c5d30e71_taxpayer_applicability.py")
    with engine.begin() as connection:
        catalog = metadata.tables["aux_tipo_contribuyente"]
        connection.execute(catalog.insert(), [
            {"codigo": code, "nombre": "Nombre editable", "activo": False}
            for code in ["01", "02", "03", "04", "05", "99"]
        ])
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()
        actual = connection.execute(sa.text(
            "SELECT codigo, aplica_persona_natural, aplica_sociedad FROM aux_tipo_contribuyente ORDER BY codigo"
        )).all()
        assert [(code, bool(natural), bool(society)) for code, natural, society in actual] == [
            ("01", True, False), ("02", False, True), ("03", True, False),
            ("04", True, True), ("05", False, True), ("99", False, False),
        ]
        with Operations.context(context):
            migration.downgrade()
        assert connection.scalar(sa.select(sa.func.count()).select_from(catalog)) == 6


def test_directory_migration_upgrade_downgrade_preserves_data():
    engine, metadata = _database()
    with engine.begin() as connection:
        persona = metadata.tables["tbl_persona"]
        connection.execute(persona.insert(), {"id": str(uuid4()), "activo": False, "identificacion": "Ab123"})
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            _migration().upgrade()
        with pytest.raises(sa.exc.IntegrityError):
            with connection.begin_nested():
                connection.execute(persona.insert(), {"id": str(uuid4()), "activo": True, "identificacion": " ab123 "})
        with Operations.context(context):
            _migration().downgrade()
        assert connection.scalar(sa.select(persona.c.identificacion)) == "Ab123"
        assert connection.scalar(sa.select(sa.func.count()).select_from(persona)) == 1


@pytest.mark.parametrize("table,key,values", [
    ("tbl_proveedor_persona", "persona_id", ["persona", "persona"]),
    ("tbl_usuario", "username", ["Andrea", " andrea "]),
    ("tbl_tipo_cliente", "nombre", ["Mayorista", " mayorista "]),
    ("tbl_persona", "identificacion", ["ab123", " AB123 "]),
])
def test_directory_migration_refuses_conflicts_before_schema_changes(table, key, values):
    engine, metadata = _database()
    with engine.begin() as connection:
        for value in values:
            row = {"id": str(uuid4()), "activo": False, key: value}
            if table == "tbl_usuario":
                row["persona_id"] = str(uuid4())
            connection.execute(metadata.tables[table].insert(), row)
        context = MigrationContext.configure(connection)
        with Operations.context(context), pytest.raises(RuntimeError, match="duplicados normalizados"):
            _migration().upgrade()
        assert not sa.inspect(connection).get_indexes("tbl_proveedor_persona")
        assert connection.scalar(sa.select(sa.func.count()).select_from(metadata.tables[table])) == 2


@pytest.mark.skipif(not os.getenv("DIRECTORY_TEST_DATABASE_URL"), reason="Requiere PostgreSQL de prueba autorizado")
def test_directory_uniqueness_upgrade_and_downgrade_on_postgresql():
    engine = sa.create_engine(os.environ["DIRECTORY_TEST_DATABASE_URL"])
    schema = f"directory_test_{uuid4().hex}"
    migration = _migration()
    catalog_migration = _migration("f8b2c5d30e71_taxpayer_applicability.py")
    rbac_migration = _migration("a9c3d6e41f82_directory_rbac_bootstrap.py")
    try:
        with engine.begin() as connection:
            connection.execute(sa.schema.CreateSchema(schema))
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
            _, metadata = _database()
            metadata.create_all(connection)
            from osiris.modules.common.rol.entity import Rol
            from osiris.modules.common.modulo.entity import Modulo
            from osiris.modules.common.rol_modulo_permiso.entity import RolModuloPermiso

            for model in (Rol, Modulo, RolModuloPermiso):
                model.__table__.create(connection)
            administrator = Rol(nombre="Administrador", usuario_auditoria="test")
            connection.execute(Rol.__table__.insert(), administrator.model_dump())
            connection.execute(metadata.tables["aux_tipo_contribuyente"].insert(), [
                {"codigo": code, "nombre": "Editable", "activo": True}
                for code in ["01", "02", "03", "04", "05", "99"]
            ])
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.upgrade()
                catalog_migration.upgrade()
                rbac_migration.upgrade()
                rbac_migration.upgrade()
            assert connection.scalar(sa.select(sa.func.count()).select_from(RolModuloPermiso.__table__)) == 7
            assert connection.execute(sa.text(
                "SELECT codigo FROM aux_tipo_contribuyente WHERE aplica_persona_natural ORDER BY codigo"
            )).scalars().all() == ["01", "03", "04"]
            assert connection.execute(sa.text(
                "SELECT codigo FROM aux_tipo_contribuyente WHERE aplica_sociedad ORDER BY codigo"
            )).scalars().all() == ["02", "04", "05"]
            for table_name, field, _, _ in migration.INDEXES:
                table = metadata.tables[table_name]
                original = "Andrea" if field != "persona_id" else str(uuid4())
                duplicate = " andrea " if field != "persona_id" else original
                row = {"id": str(uuid4()), "activo": False, field: original}
                if table_name == "tbl_usuario":
                    row["persona_id"] = str(uuid4())
                connection.execute(table.insert(), row)
                row = {"id": str(uuid4()), "activo": True, field: duplicate}
                if table_name == "tbl_usuario":
                    row["persona_id"] = str(uuid4())
                with pytest.raises(sa.exc.IntegrityError):
                    with connection.begin_nested():
                        connection.execute(table.insert(), row)
            with Operations.context(context):
                rbac_migration.downgrade()
                catalog_migration.downgrade()
                migration.downgrade()
            assert connection.scalar(sa.select(sa.func.count()).select_from(metadata.tables["tbl_usuario"])) == 1
            connection.execute(sa.schema.DropSchema(schema, cascade=True))
    finally:
        engine.dispose()