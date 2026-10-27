from __future__ import annotations

import importlib.util
import os
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from io import StringIO
from pathlib import Path
from threading import Event
from types import ModuleType
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

pytestmark = pytest.mark.filterwarnings(
    "ignore:Skipped unsupported reflection of expression-based index:sqlalchemy.exc.SAWarning"
)

VERSIONS = Path(__file__).parents[1] / "src/osiris/db/alembic/versions"


def _load(filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), VERSIONS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (" Resolucion optica ", "resolucion_optica"),
        ("Resoluci\u00f3n / \u00d3ptica", "resolucion_optica"),
        ("123 ancho", "atributo_123_ancho"),
        ("---", "atributo"),
        ("\u4e2d\u6587", "atributo"),
        ("a" * 120, "a" * 120),
    ],
)
def test_frozen_attribute_code(name: str, expected: str) -> None:
    migration = _load("e1a6c2d9b740_add_attribute_unit_catalog.py")
    assert migration._attribute_code(name) == expected


def test_attribute_code_does_not_silently_truncate() -> None:
    migration = _load("e1a6c2d9b740_add_attribute_unit_catalog.py")
    with pytest.raises(RuntimeError, match="120"):
        migration._attribute_code("a" * 121)


UNIT_REVISION = "e1a6c2d9b740_add_attribute_unit_catalog.py"
HISTORY_REVISION = "e2b7d3f0c851_catalog_historical_identity.py"
AUDIT_NULLABILITY_REVISION = "f04b7c2a9e61_align_catalog_audit_nullability.py"
STAMP = datetime(2026, 10, 25)


def _audit_columns() -> list[sa.Column[Any]]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(255)),
        sa.Column("updated_by", sa.String(255)),
        sa.Column("usuario_auditoria", sa.String(255)),
    ]


def _legacy_schema(engine: Engine) -> None:
    metadata = sa.MetaData()
    sa.Table("tbl_catalogo", metadata, *_audit_columns())
    attributes = sa.Table(
        "tbl_atributo", metadata, *_audit_columns(),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("tipo_dato", sa.Enum("STRING", "INTEGER", "DECIMAL", "BOOLEAN", "DATE",
                                     "SELECT", "CATALOG", name="tipodato"), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("select_options", sa.JSON()),
        sa.Column("catalog_id", sa.Uuid(), sa.ForeignKey("tbl_catalogo.id")),
        sa.Column("allow_negative", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("min_value", sa.Numeric(18, 6)),
        sa.Column("max_value", sa.Numeric(18, 6)),
    )
    sa.Index("uq_tbl_atributo_nombre_activo", sa.func.lower(sa.func.trim(attributes.c.nombre)),
             unique=True, sqlite_where=attributes.c.activo.is_(True),
             postgresql_where=attributes.c.activo.is_(True))
    sa.Table(
        "tbl_categoria", metadata, *_audit_columns(),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), sa.ForeignKey("tbl_categoria.id")),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("es_padre", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    mappings = sa.Table(
        "tbl_categoria_atributo", metadata, *_audit_columns(),
        sa.Column("categoria_id", sa.Uuid(), sa.ForeignKey("tbl_categoria.id"), nullable=False),
        sa.Column("atributo_id", sa.Uuid(), sa.ForeignKey("tbl_atributo.id"), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("orden", sa.Integer()), sa.Column("obligatorio", sa.Boolean()),
        sa.Column("valor_default", sa.String()),
    )
    sa.Index("uq_categoria_atributo_activo", mappings.c.categoria_id, mappings.c.atributo_id,
             unique=True, sqlite_where=mappings.c.activo.is_(True),
             postgresql_where=mappings.c.activo.is_(True))
    sa.Table("tbl_producto", metadata, *_audit_columns(), sa.Column("nombre", sa.String()),
             sa.Column("activo", sa.Boolean(), server_default=sa.true()))
    sa.Table(
        "tbl_producto_categoria", metadata, *_audit_columns(),
        sa.Column("producto_id", sa.Uuid(), sa.ForeignKey("tbl_producto.id")),
        sa.Column("categoria_id", sa.Uuid(), sa.ForeignKey("tbl_categoria.id")),
    )
    sa.Table(
        "tbl_producto_atributo_valor", metadata, *_audit_columns(),
        sa.Column("producto_id", sa.Uuid(), sa.ForeignKey("tbl_producto.id")),
        sa.Column("atributo_id", sa.Uuid(), sa.ForeignKey("tbl_atributo.id")),
        sa.Column("activo", sa.Boolean(), server_default=sa.true()),
        sa.Column("valor_string", sa.String()), sa.Column("valor_integer", sa.Integer()),
        sa.Column("valor_decimal", sa.Numeric(18, 6)), sa.Column("valor_boolean", sa.Boolean()),
        sa.Column("valor_date", sa.Date()),
    )
    metadata.create_all(engine)
    _run(engine, _load("c5e91a7d2b64_add_attribute_change_snapshots.py").upgrade)


@pytest.fixture(params=["sqlite", "postgresql"])
def database(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[Engine]:
    if request.param == "sqlite":
        engine = sa.create_engine(sa.URL.create("sqlite", database=str(tmp_path / "catalog.db")))

        @sa.event.listens_for(engine, "connect")
        def sqlite_connect(dbapi: Any, record: Any) -> None:
            dbapi.isolation_level = None
            dbapi.execute("PRAGMA foreign_keys=ON")

        @sa.event.listens_for(engine, "begin")
        def sqlite_begin(connection: Connection) -> None:
            connection.exec_driver_sql("BEGIN")

        try:
            _legacy_schema(engine)
            yield engine
        finally:
            engine.dispose()
        return
    url = os.environ.get("CATALOG_TEST_DATABASE_URL")
    if not url:
        pytest.skip("PostgreSQL opt-in: CATALOG_TEST_DATABASE_URL is not configured")
    try:
        parsed = sa.engine.make_url(url)
        if parsed.get_backend_name() != "postgresql":
            raise ValueError
        admin = sa.create_engine(parsed.set(drivername="postgresql+psycopg"),
                                 hide_parameters=True, connect_args={"connect_timeout": 5})
    except Exception:
        pytest.fail("Invalid isolated PostgreSQL test configuration", pytrace=False)
    schema = "catalog_migration_test_" + uuid4().hex
    with admin.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    engine = sa.create_engine(admin.url, hide_parameters=True, connect_args={"connect_timeout": 5})

    @sa.event.listens_for(engine, "connect")
    def postgres_connect(dbapi: Any, record: Any) -> None:
        previous = dbapi.autocommit
        dbapi.autocommit = True
        try:
            with dbapi.cursor() as cursor:
                cursor.execute(f'SET search_path TO "{schema}", pg_catalog')
                cursor.execute("SET lock_timeout TO '3s'")
                cursor.execute("SET statement_timeout TO '8s'")
        finally:
            dbapi.autocommit = previous

    try:
        _legacy_schema(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        admin.dispose()


def _run(engine: Engine, operation: Callable[[], None]) -> None:
    with engine.connect() as connection:
        if engine.dialect.name == "sqlite":
            _sqlite_foreign_keys(connection, False)
        try:
            with connection.begin():
                with Operations.context(MigrationContext.configure(connection)):
                    operation()
                if engine.dialect.name == "sqlite":
                    assert not connection.exec_driver_sql("PRAGMA foreign_key_check").all()
        finally:
            if engine.dialect.name == "sqlite":
                _sqlite_foreign_keys(connection, True)


def _sqlite_foreign_keys(connection: Connection, enabled: bool) -> None:
    driver = connection.connection.driver_connection
    assert driver is not None
    driver.execute("PRAGMA foreign_keys=" + ("ON" if enabled else "OFF"))


def _table(connection: Connection | Engine, name: str) -> sa.Table:
    return sa.Table(name, sa.MetaData(), autoload_with=connection)


def _insert(connection: Connection, name: str, **values: Any) -> Any:
    table = _table(connection, name)
    row_id = values.setdefault("id", uuid4())
    values.setdefault("creado_en", STAMP)
    values.setdefault("actualizado_en", STAMP)
    values = {key: value.hex if isinstance(value, UUID) and
              not isinstance(table.c[key].type, sa.Uuid) else value for key, value in values.items()}
    connection.execute(table.insert().values(**values))
    return row_id


def _upgrade(engine: Engine) -> None:
    _run(engine, _load(UNIT_REVISION).upgrade)
    _run(engine, _load(HISTORY_REVISION).upgrade)
    _run(engine, _load(AUDIT_NULLABILITY_REVISION).upgrade)


def _snapshot(connection: Connection, attribute_id: Any, **values: Any) -> Any:
    data: dict[str, Any] = {
        "atributo_id": attribute_id, "operacion": "update", "definicion_anterior": {},
        "definicion_posterior": {}, "asignaciones_anteriores": [], "asignaciones_posteriores": [],
        "valores_anteriores": [], "valores_posteriores": [], "remapeos_anteriores": [],
        "remapeos_posteriores": [], "revertido": False,
    }
    data.update(values)
    return _insert(connection, "tbl_atributo_cambio", **data)


def test_empty_upgrade_downgrade_upgrade(database: Engine) -> None:
    units = _load(UNIT_REVISION)
    history = _load(HISTORY_REVISION)
    audit_nullability = _load(AUDIT_NULLABILITY_REVISION)
    assert units.down_revision == "c5e91a7d2b64"
    assert history.down_revision == units.revision
    assert audit_nullability.down_revision == history.revision
    _upgrade(database)
    with database.connect() as connection:
        before = connection.execute(sa.text(
            "SELECT id, codigo, nombre, simbolo, magnitud_codigo, es_sistema, activo "
            "FROM tbl_unidad ORDER BY codigo"
        )).all()
        assert len(before) == 22
        for row in before:
            assert UUID(str(row.id)) == uuid5(NAMESPACE_URL, "osiris:unidad:" + row.codigo)
            assert row.es_sistema and row.activo
        assert {row.simbolo for row in before} == {
            "u", "g", "kg", "lb", "mL", "L", "mm", "cm", "m", "in", "s", "min", "h",
            "MB", "GB", "TB", "MiB", "GiB", "MHz", "GHz", "dpi", "%",
        }
    _run(database, audit_nullability.downgrade)
    _run(database, history.downgrade)
    _run(database, units.downgrade)
    assert "tbl_unidad" not in sa.inspect(database).get_table_names()
    _upgrade(database)
    with database.connect() as connection:
        assert connection.execute(sa.text(
            "SELECT id, codigo, nombre, simbolo, magnitud_codigo, es_sistema, activo "
            "FROM tbl_unidad ORDER BY codigo"
        )).all() == before


def test_catalog_audit_nullability_upgrade_and_guarded_downgrade(tmp_path: Path) -> None:
    engine = sa.create_engine(sa.URL.create("sqlite", database=str(tmp_path / "audit.db")))
    metadata = sa.MetaData()
    tables = [
        sa.Table(
            name,
            metadata,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("usuario_auditoria", sa.String(255), nullable=False),
        )
        for name in ("tbl_atributo", "tbl_categoria", "tbl_categoria_atributo")
    ]
    metadata.create_all(engine)
    with engine.begin() as connection:
        for table in tables:
            connection.execute(table.insert().values(usuario_auditoria="test-actor"))

    migration = _load(AUDIT_NULLABILITY_REVISION)
    _run(engine, migration.upgrade)
    assert all(
        next(column for column in sa.inspect(engine).get_columns(table.name)
             if column["name"] == "usuario_auditoria")["nullable"]
        for table in tables
    )
    with engine.begin() as connection:
        connection.execute(
            tables[0].update().values(usuario_auditoria=None).where(tables[0].c.id == 1)
        )
    with pytest.raises(RuntimeError, match="null values exist"):
        _run(engine, migration.downgrade)
    assert all(
        next(column for column in sa.inspect(engine).get_columns(table.name)
             if column["name"] == "usuario_auditoria")["nullable"]
        for table in tables
    )
    with engine.begin() as connection:
        connection.execute(tables[0].update().values(usuario_auditoria="restored"))
    _run(engine, migration.downgrade)
    assert not any(
        next(column for column in sa.inspect(engine).get_columns(table.name)
             if column["name"] == "usuario_auditoria")["nullable"]
        for table in tables
    )
    engine.dispose()


@pytest.mark.parametrize("conflict", ["active_name", "code", "empty_code", "too_long",
                                     "root", "child", "mapping", "cycle", "missing_parent",
                                     "inactive_parent", "default_root"])
def test_preflight_blocks_before_any_ddl(database: Engine, conflict: str) -> None:
    if conflict == "missing_parent" and database.dialect.name == "sqlite":
        with database.connect() as connection:
            _sqlite_foreign_keys(connection, False)
    with database.begin() as connection:
        first = _insert(connection, "tbl_atributo", nombre="Ancho", tipo_dato="INTEGER")
        parent = _insert(connection, "tbl_categoria", nombre="Raiz")
        if conflict == "active_name":
            connection.exec_driver_sql("DROP INDEX uq_tbl_atributo_nombre_activo")
            _insert(connection, "tbl_atributo", nombre=" ancho ", tipo_dato="INTEGER")
        elif conflict in {"code", "empty_code"}:
            names = ("Largo-ancho", "Largo ancho") if conflict == "code" else ("---", "!!!")
            for name in names:
                _insert(connection, "tbl_atributo", nombre=name, tipo_dato="INTEGER", activo=False)
        elif conflict == "too_long":
            connection.execute(_table(connection, "tbl_atributo").update().values(
                nombre="1" + "a" * 119))
        elif conflict in {"root", "child"}:
            for active in (True, False):
                _insert(connection, "tbl_categoria", nombre=" Duplicado ", activo=active,
                        parent_id=parent if conflict == "child" else None)
        elif conflict == "mapping":
            for active in (True, False):
                _insert(connection, "tbl_categoria_atributo", categoria_id=parent,
                        atributo_id=first, activo=active)
        elif conflict == "cycle":
            child = _insert(connection, "tbl_categoria", nombre="Hijo", parent_id=parent)
            connection.execute(_table(connection, "tbl_categoria").update().values(
                parent_id=str(child).replace("-", "") if database.dialect.name == "sqlite"
                else child).where(sa.text("nombre = 'Raiz'")))
        elif conflict == "missing_parent":
            if database.dialect.name == "postgresql":
                connection.exec_driver_sql(
                    "ALTER TABLE tbl_categoria DROP CONSTRAINT tbl_categoria_parent_id_fkey")
            _insert(connection, "tbl_categoria", nombre="Huerfano", parent_id=uuid4())
        elif conflict == "inactive_parent":
            connection.execute(_table(connection, "tbl_categoria").update().values(activo=False))
            _insert(connection, "tbl_categoria", nombre="Hijo", parent_id=parent)
        else:
            connection.execute(_table(connection, "tbl_categoria").update().values(is_default=True))
    with pytest.raises(RuntimeError, match="before DDL"):
        _run(database, _load(UNIT_REVISION).upgrade)
    assert "tbl_unidad" not in sa.inspect(database).get_table_names()
    assert "codigo" not in {column["name"] for column in
                            sa.inspect(database).get_columns("tbl_atributo")}


def test_upgrade_preserves_legacy_history_and_reconciles_parent_flags(database: Engine) -> None:
    with database.begin() as connection:
        attribute = _insert(connection, "tbl_atributo", nombre="Resoluci\u00f3n", tipo_dato="INTEGER")
        parent = _insert(connection, "tbl_categoria", nombre="Raiz", es_padre=False)
        child = _insert(connection, "tbl_categoria", nombre="Hijo", parent_id=parent, es_padre=True)
        _insert(connection, "tbl_categoria", nombre="Inactivo", parent_id=child, activo=False)
        mapping = _insert(connection, "tbl_categoria_atributo", categoria_id=child,
                          atributo_id=attribute, activo=False, valor_default="42", orden=3)
        snapshot = _snapshot(connection, attribute, definicion_anterior={"nombre": "Resolucion"})
        product = _insert(connection, "tbl_producto", nombre="Producto")
        _insert(connection, "tbl_producto_categoria", producto_id=product, categoria_id=child)
        value = _insert(connection, "tbl_producto_atributo_valor", producto_id=product,
                        atributo_id=attribute, valor_integer=42, activo=False)
        preserved = {name: connection.execute(sa.select(_table(connection, name))).all()
                     for name in ("tbl_categoria_atributo", "tbl_atributo_cambio", "tbl_producto",
                                  "tbl_producto_categoria", "tbl_producto_atributo_valor")}
    _upgrade(database)
    with database.connect() as connection:
        attributes = _table(connection, "tbl_atributo")
        row = connection.execute(sa.select(attributes)).mappings().one()
        assert UUID(str(row["id"])) == UUID(str(attribute))
        assert row["codigo"] == "resolucion" and row["unidad_id"] is None
        flags = {name: flag for name, flag in connection.execute(
            sa.text("SELECT nombre, es_padre FROM tbl_categoria"))}
        assert flags == {"Raiz": True, "Hijo": False, "Inactivo": False}
        for name, rows in preserved.items():
            assert connection.execute(sa.select(_table(connection, name))).all() == rows
        assert mapping and snapshot and value
    for filename in (HISTORY_REVISION, UNIT_REVISION):
        with pytest.raises(RuntimeError, match="Cannot downgrade"):
            _run(database, _load(filename).downgrade)


@pytest.mark.parametrize("kind", ["STRING", "BOOLEAN", "DATE", "SELECT", "CATALOG"])
def test_unit_fk_numeric_check_and_not_null(database: Engine, kind: str) -> None:
    _upgrade(database)
    with database.connect() as connection:
        unit_id = connection.execute(sa.text("SELECT id FROM tbl_unidad WHERE codigo='UNIDAD'"))
        unit = unit_id.scalar_one()
    with pytest.raises(IntegrityError), database.begin() as connection:
        _insert(connection, "tbl_atributo", nombre="Invalido", codigo="invalido",
                tipo_dato=kind, unidad_id=unit)
    for numeric in ("INTEGER", "DECIMAL"):
        with database.begin() as connection:
            _insert(connection, "tbl_atributo", nombre=numeric, codigo=numeric.lower(),
                    tipo_dato=numeric, unidad_id=unit)
    with pytest.raises(IntegrityError), database.begin() as connection:
        _insert(connection, "tbl_atributo", nombre="Sin codigo", tipo_dato="INTEGER")
    with pytest.raises(IntegrityError), database.begin() as connection:
        _insert(connection, "tbl_atributo", nombre="Sin unidad", codigo="sin_unidad",
                tipo_dato="INTEGER", unidad_id=uuid4())
    with pytest.raises(IntegrityError), database.begin() as connection:
        connection.execute(_table(connection, "tbl_unidad").delete())


@pytest.mark.parametrize("identity", ["root", "child", "mapping", "attribute_code",
                                     "attribute_name", "unit_code", "unit_symbol"])
def test_direct_sql_historical_uniqueness(database: Engine, identity: str) -> None:
    _upgrade(database)
    with database.begin() as connection:
        parent = _insert(connection, "tbl_categoria", nombre="Padre")
        attribute = _insert(connection, "tbl_atributo", nombre="Medida", codigo="medida",
                            tipo_dato="INTEGER", activo=False)
        if identity in {"root", "child"}:
            table, first, second = "tbl_categoria", {
                "nombre": "Duplicado", "activo": False,
                "parent_id": parent if identity == "child" else None,
            }, {"nombre": " duplicado ", "activo": True,
                "parent_id": parent if identity == "child" else None}
        elif identity == "mapping":
            table, first, second = "tbl_categoria_atributo", {
                "categoria_id": parent, "atributo_id": attribute, "activo": False,
            }, {"categoria_id": parent, "atributo_id": attribute, "activo": True}
        elif identity.startswith("attribute"):
            table = "tbl_atributo"
            first = {"nombre": "Nuevo", "codigo": "nuevo", "tipo_dato": "INTEGER"}
            second = {"nombre": "Otro", "codigo": "nuevo", "tipo_dato": "INTEGER"}
            if identity == "attribute_name":
                second.update(nombre=" nuevo ", codigo="otro")
        else:
            table = "tbl_unidad"
            first = {"nombre": "Custom", "codigo": "CUSTOM", "simbolo": "Zz",
                     "magnitud_codigo": "CUSTOM", "es_sistema": False, "activo": False}
            second = dict(first, codigo="custom" if identity == "unit_code" else "OTHER",
                          simbolo="other" if identity == "unit_code" else "Zz", activo=True)
        _insert(connection, table, **first)
    with pytest.raises(IntegrityError), database.begin() as connection:
        _insert(connection, table, **second)


def test_symbol_case_is_sensitive_and_code_survives_rename(database: Engine) -> None:
    _upgrade(database)
    with database.begin() as connection:
        _insert(connection, "tbl_unidad", nombre="Megabit", codigo="MEGABIT", simbolo="Mb",
                magnitud_codigo="DATA_STORAGE", es_sistema=False, activo=True)
        _insert(connection, "tbl_atributo", nombre="Antes", codigo="estable", tipo_dato="INTEGER")
        connection.execute(_table(connection, "tbl_atributo").update().values(nombre="Despues"))
        assert connection.execute(sa.text("SELECT codigo FROM tbl_atributo")).scalar_one() == "estable"


def test_unit_downgrade_guards_custom_history(database: Engine) -> None:
    _run(database, _load(UNIT_REVISION).upgrade)
    with database.begin() as connection:
        _insert(connection, "tbl_unidad", nombre="Historial", codigo="HISTORY", simbolo="hist",
                magnitud_codigo="CUSTOM", es_sistema=False, activo=False)
    with pytest.raises(RuntimeError, match="unit history"):
        _run(database, _load(UNIT_REVISION).downgrade)


@pytest.mark.parametrize("field", ["nombre", "updated_by", "activo"])
def test_unit_downgrade_guards_modified_seeds(database: Engine, field: str) -> None:
    _run(database, _load(UNIT_REVISION).upgrade)
    with database.begin() as connection:
        connection.execute(_table(connection, "tbl_unidad").update().values(
            **{field: False if field == "activo" else "modified"}))
    with pytest.raises(RuntimeError, match="modified unit history"):
        _run(database, _load(UNIT_REVISION).downgrade)
    assert "tbl_unidad" in sa.inspect(database).get_table_names()


@pytest.mark.parametrize("conflict", ["root", "child", "mapping", "cycle", "active_name"])
def test_historical_revision_rechecks_before_ddl(database: Engine, conflict: str) -> None:
    _run(database, _load(UNIT_REVISION).upgrade)
    with database.begin() as connection:
        parent = _insert(connection, "tbl_categoria", nombre="Padre")
        attribute = _insert(connection, "tbl_atributo", nombre="Uno", codigo="uno",
                            tipo_dato="INTEGER")
        if conflict in {"root", "child"}:
            for active in (False, True):
                _insert(connection, "tbl_categoria", nombre=" Duplicado ", activo=active,
                        parent_id=parent if conflict == "child" else None)
        elif conflict == "mapping":
            for active in (False, True):
                _insert(connection, "tbl_categoria_atributo", categoria_id=parent,
                        atributo_id=attribute, activo=active)
        elif conflict == "cycle":
            table = _table(connection, "tbl_categoria")
            connection.execute(table.update().values(parent_id=parent.hex if
                               database.dialect.name == "sqlite" else parent))
        else:
            connection.exec_driver_sql("DROP INDEX uq_tbl_atributo_nombre_activo")
            _insert(connection, "tbl_atributo", nombre=" uno ", codigo="dos", tipo_dato="INTEGER")
        before = connection.execute(sa.select(_table(connection, "tbl_categoria"))).all()
    with pytest.raises(RuntimeError, match="before DDL"):
        _run(database, _load(HISTORY_REVISION).upgrade)
    with database.connect() as connection:
        assert connection.execute(sa.select(_table(connection, "tbl_categoria"))).all() == before
        constraints = sa.inspect(connection).get_unique_constraints("tbl_categoria_atributo")
        assert "uq_categoria_atributo_historical" not in {item["name"] for item in constraints}


def test_sqlite_batch_requires_fk_toggle_before_transaction(database: Engine) -> None:
    if database.dialect.name != "sqlite":
        pytest.skip("SQLite-specific batch precondition")
    with database.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            with pytest.raises(RuntimeError, match="before DDL"):
                _load(UNIT_REVISION).upgrade()
    assert "tbl_unidad" not in sa.inspect(database).get_table_names()


def test_frozen_v2_unit_catalog() -> None:
    migration = _load(UNIT_REVISION)
    expected = {
        "UNIDAD": ("u", "COUNT"), "GRAMO": ("g", "MASS"),
        "KILOGRAMO": ("kg", "MASS"), "LIBRA": ("lb", "MASS"),
        "MILILITRO": ("mL", "VOLUME"), "LITRO": ("L", "VOLUME"),
        "MILIMETRO": ("mm", "LENGTH"), "CENTIMETRO": ("cm", "LENGTH"),
        "METRO": ("m", "LENGTH"), "PULGADA": ("in", "LENGTH"),
        "SEGUNDO": ("s", "TIME"), "MINUTO": ("min", "TIME"), "HORA": ("h", "TIME"),
        "MEGABYTE": ("MB", "DATA_STORAGE"), "GIGABYTE": ("GB", "DATA_STORAGE"),
        "TERABYTE": ("TB", "DATA_STORAGE"), "MEBIBYTE": ("MiB", "DATA_STORAGE"),
        "GIBIBYTE": ("GiB", "DATA_STORAGE"), "MEGAHERCIO": ("MHz", "FREQUENCY"),
        "GIGAHERCIO": ("GHz", "FREQUENCY"),
        "PUNTOS_POR_PULGADA": ("dpi", "RESOLUTION_DENSITY"),
        "PORCENTAJE": ("%", "PERCENTAGE"),
    }
    assert len(migration.UNITS_V2) == 22
    assert {code: (symbol, magnitude) for code, name, symbol, magnitude in
            migration.UNITS_V2} == expected


def test_postgresql_ddl_rendering_without_database(monkeypatch: pytest.MonkeyPatch) -> None:
    units, history = _load(UNIT_REVISION), _load(HISTORY_REVISION)
    monkeypatch.setattr(units, "_preflight", lambda connection: [])
    monkeypatch.setattr(history, "_preflight", lambda connection: None)
    buffer = StringIO()
    context = MigrationContext.configure(dialect_name="postgresql", opts={
        "as_sql": True, "output_buffer": buffer,
    })
    with Operations.context(context):
        units.upgrade()
        history.upgrade()
    sql = buffer.getvalue()
    assert 'simbolo VARCHAR(32) COLLATE "C" NOT NULL' in sql
    assert "lower(CAST(tipo_dato AS TEXT)) IN ('integer', 'decimal')" in sql
    assert "ALTER COLUMN codigo SET NOT NULL" in sql
    assert "FOREIGN KEY(unidad_id) REFERENCES tbl_unidad (id)" in sql
    assert "UNIQUE (categoria_id, atributo_id)" in sql
    assert "WHERE parent_id IS NULL" in sql and "WHERE parent_id IS NOT NULL" in sql
    assert "DROP " not in sql
    assert "'MB'" in sql and "'MiB'" in sql and "'GHz'" in sql


@pytest.mark.parametrize("identity", ["root", "child", "mapping", "attribute_code",
                                     "unit_code", "unit_symbol"])
@pytest.mark.parametrize("rollback_first", [False, True])
def test_two_postgresql_sessions(database: Engine, identity: str, rollback_first: bool) -> None:
    if database.dialect.name != "postgresql":
        pytest.skip("Two-session uniqueness requires PostgreSQL")
    _upgrade(database)
    with database.begin() as connection:
        parent = _insert(connection, "tbl_categoria", nombre="Padre")
        attribute = _insert(connection, "tbl_atributo", nombre="Medida", codigo="medida",
                            tipo_dato="INTEGER")
    if identity in {"root", "child"}:
        name = "tbl_categoria"
        values = {"nombre": "Carrera", "parent_id": parent if identity == "child" else None}
        contender = dict(values, nombre=" carrera ")
    elif identity == "mapping":
        name = "tbl_categoria_atributo"
        values = {"categoria_id": parent, "atributo_id": attribute}
        contender = dict(values)
    elif identity == "attribute_code":
        name = "tbl_atributo"
        values = {"nombre": "Primero", "codigo": "carrera", "tipo_dato": "INTEGER"}
        contender = dict(values, nombre="Segundo")
    else:
        name = "tbl_unidad"
        values = {"nombre": "Carrera", "codigo": "RACE", "simbolo": "race",
                  "magnitud_codigo": "CUSTOM", "es_sistema": False, "activo": True}
        contender = dict(values, codigo="race" if identity == "unit_code" else "SECOND",
                         simbolo="second" if identity == "unit_code" else "race")
    table = _table(database, name)
    blocked = Event()
    release = Event()

    def insert_second() -> str:
        with Session(database) as session:
            statement = table.insert().values(id=uuid4(), creado_en=STAMP,
                                              actualizado_en=STAMP, **contender)
            session.execute(sa.text("SET LOCAL lock_timeout TO '250ms'"))
            try:
                session.execute(statement)
            except OperationalError as exc:
                assert getattr(exc.orig, "sqlstate", None) == "55P03"
                session.rollback()
                blocked.set()
            else:
                session.rollback()
                raise AssertionError("Contender did not wait for the uncommitted unique identity")
            assert release.wait(timeout=5)
            try:
                session.execute(statement)
                session.commit()
                return "committed"
            except IntegrityError:
                session.rollback()
                return "conflict"

    with Session(database) as first_session, ThreadPoolExecutor(max_workers=1) as executor:
        first_session.execute(table.insert().values(id=uuid4(), creado_en=STAMP,
                                                   actualizado_en=STAMP, **values))
        future = executor.submit(insert_second)
        try:
            assert blocked.wait(timeout=3)
            if rollback_first:
                first_session.rollback()
            else:
                first_session.commit()
        finally:
            release.set()
        assert future.result(timeout=10) == ("committed" if rollback_first else "conflict")