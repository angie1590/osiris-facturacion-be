from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
import os
from threading import Barrier
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock
from uuid import uuid4

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from osiris.domain.service import BaseService
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.catalogo.entity import Catalogo
from osiris.modules.common.unidad.entity import Unidad
from osiris.modules.inventario.atributo.entity import Atributo, TipoDato
from osiris.modules.inventario.atributo.repository import AtributoRepository
from osiris.modules.inventario.atributo.service import AtributoService


NAME_INDEX = "uq_tbl_atributo_nombre_activo_normalized"
CODE_INDEX = "uq_tbl_atributo_codigo_normalizado"


def _create_tables(engine: Engine, schema: str | None = None) -> None:
    metadata = sa.MetaData()
    for model in (Unidad, Catalogo, Atributo, AuditLog):
        source = sa.inspect(model).local_table
        assert isinstance(source, sa.Table)
        table = source.to_metadata(metadata)
        for constraint in source.constraints:
            condition = getattr(constraint, "_ddl_if", None)
            if (
                isinstance(constraint, sa.CheckConstraint)
                and condition is not None
                and engine.dialect.name != condition.dialect
            ):
                for copied in list(table.constraints):
                    if isinstance(copied, sa.CheckConstraint) and (
                        str(copied.sqltext) == str(constraint.sqltext)
                    ):
                        table.constraints.remove(copied)
        for column in table.columns:
            if isinstance(column.type, sa.Enum):
                column.type = sa.Enum(
                    *column.type.enums, name=column.type.name, schema=schema
                )
    attribute = metadata.tables["tbl_atributo"]
    code_index = next(index for index in attribute.indexes if index.name == CODE_INDEX)
    attribute.indexes.remove(code_index)
    metadata.create_all(engine)
    code_index.create(engine)


@pytest.fixture
def sqlite_session() -> Iterator[Session]:
    engine = sa.create_engine("sqlite://")
    try:
        _create_tables(engine)
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def _name_integrity_error() -> IntegrityError:
    original = RuntimeError(NAME_INDEX)
    return IntegrityError("INSERT INTO tbl_atributo", {}, original)


def _skip_first_code_check(monkeypatch: pytest.MonkeyPatch) -> Mock:
    validate = AtributoService._validate_unique_code
    calls = 0

    def check(session: Session, code: str) -> None:
        nonlocal calls
        calls += 1
        if calls > 1:
            validate(session, code)

    wrapped = Mock(side_effect=check)
    monkeypatch.setattr(AtributoService, "_validate_unique_code", staticmethod(wrapped))
    monkeypatch.setattr(AtributoService, "_validate_unique_name", Mock())
    return wrapped


@pytest.mark.parametrize("depth", [0, 1, 2])
@pytest.mark.parametrize("active", [True, False])
def test_create_rechecks_original_and_chained_integrity_errors(
    sqlite_session: Session, monkeypatch: pytest.MonkeyPatch, depth: int, active: bool
) -> None:
    service = AtributoService()
    service.create(
        sqlite_session, {"nombre": "RAM", "tipo_dato": TipoDato.STRING, "activo": active}
    )
    integrity = _name_integrity_error()
    error: Exception = integrity
    for _ in range(depth):
        translated = HTTPException(status_code=409, detail="translated")
        translated.__cause__ = error
        error = translated
    monkeypatch.setattr(BaseService, "create", Mock(side_effect=error))
    check = _skip_first_code_check(monkeypatch)
    payload = {"nombre": "RAM", "tipo_dato": TipoDato.STRING}

    with pytest.raises(HTTPException) as caught:
        service.create(sqlite_session, payload)

    assert caught.value.status_code == 409
    assert isinstance(caught.value.detail, dict)
    assert caught.value.detail["code"] == "ATTRIBUTE_DUPLICATE_CODE"
    assert check.call_count == 2
    assert payload == {"nombre": "RAM", "tipo_dato": TipoDato.STRING}
    assert not sqlite_session.new


def test_create_handles_real_repository_flush_conflict(
    sqlite_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = AtributoService()
    service.create(sqlite_session, {"nombre": "RAM", "tipo_dato": TipoDato.STRING})
    check = _skip_first_code_check(monkeypatch)

    with pytest.raises(HTTPException) as caught:
        service.create(sqlite_session, {"nombre": "RAM", "tipo_dato": TipoDato.STRING})

    assert caught.value.status_code == 409
    assert isinstance(caught.value.detail, dict)
    assert caught.value.detail["code"] == "ATTRIBUTE_DUPLICATE_CODE"
    assert check.call_count == 2
    assert len(sqlite_session.exec(select(Atributo)).all()) == 1
    assert len(sqlite_session.exec(select(AuditLog)).all()) == 1


def test_create_preserves_name_conflict_without_existing_code(
    sqlite_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    integrity = _name_integrity_error()
    monkeypatch.setattr(BaseService, "create", Mock(side_effect=integrity))

    with pytest.raises(HTTPException) as caught:
        AtributoService().create(
            sqlite_session, {"nombre": "RAM", "tipo_dato": TipoDato.STRING}
        )

    assert caught.value.status_code == 409
    assert isinstance(caught.value.detail, dict)
    assert caught.value.detail["code"] == "ATTRIBUTE_DUPLICATE_NAME"
    assert caught.value.__cause__ is integrity


def test_create_preserves_rollback_error(
    sqlite_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(BaseService, "create", Mock(side_effect=_name_integrity_error()))
    failure = RuntimeError("rollback failed")
    monkeypatch.setattr(sqlite_session, "rollback", Mock(side_effect=failure))
    check = _skip_first_code_check(monkeypatch)

    with pytest.raises(RuntimeError) as caught:
        AtributoService().create(
            sqlite_session, {"nombre": "RAM", "tipo_dato": TipoDato.STRING}
        )

    assert caught.value is failure
    assert check.call_count == 1


@pytest.mark.parametrize("diagnostic", [True, False])
def test_repository_maps_name_index_with_original_cause(diagnostic: bool) -> None:
    original = RuntimeError("unique violation" if diagnostic else NAME_INDEX)
    if diagnostic:
        setattr(original, "diag", SimpleNamespace(constraint_name=NAME_INDEX))
    integrity = IntegrityError("UPDATE tbl_atributo", {}, original)

    with pytest.raises(HTTPException) as caught:
        AtributoRepository()._raise_integrity(integrity)

    assert caught.value.status_code == 409
    assert isinstance(caught.value.detail, dict)
    assert caught.value.detail["code"] == "ATTRIBUTE_DUPLICATE_NAME"
    assert caught.value.__cause__ is integrity


@pytest.fixture
def postgresql_engine() -> Iterator[Engine]:
    url = os.getenv("CATALOG_TEST_DATABASE_URL")
    if not url:
        pytest.skip("PostgreSQL opt-in: CATALOG_TEST_DATABASE_URL is not configured")
    parsed = sa.engine.make_url(url)
    if parsed.get_backend_name() != "postgresql":
        pytest.fail("CATALOG_TEST_DATABASE_URL must point to PostgreSQL")
    admin = sa.create_engine(
        parsed.set(drivername="postgresql+psycopg"),
        hide_parameters=True,
        connect_args={
            "connect_timeout": 5,
            "options": "-c lock_timeout=3000 -c statement_timeout=10000",
        },
    )
    schema = "attribute_code_test_" + uuid4().hex
    engine = admin.execution_options(schema_translate_map={None: schema})
    try:
        with admin.begin() as connection:
            connection.execute(sa.schema.CreateSchema(schema))
        try:
            _create_tables(engine, schema)
            yield engine
        finally:
            with admin.begin() as connection:
                connection.execute(sa.schema.DropSchema(schema, cascade=True))
    finally:
        admin.dispose()


@pytest.mark.parametrize(
    "names", [("Memoria RAM", "Memoria RAM"), ("Memoria RAM", "Memoria-RAM")],
    ids=["same-name-name-index-first", "different-names-same-code"],
)
def test_postgresql_concurrent_service_create_returns_duplicate_code(
    postgresql_engine: Engine, monkeypatch: pytest.MonkeyPatch, names: tuple[str, str]
) -> None:
    validated = Barrier(2)
    inserting = Barrier(2)
    validate = AtributoService._validate_unique_code
    integrity_errors: list[IntegrityError] = []
    translate = AtributoRepository._raise_integrity

    def check(session: Session, code: str) -> None:
        validate(session, code)
        if not session.info.get("code_validated"):
            session.info["code_validated"] = True
            validated.wait(timeout=10)

    def before_insert(mapper: Any, connection: Connection, attribute: Atributo) -> None:
        inserting.wait(timeout=10)

    def capture(repository: AtributoRepository, error: IntegrityError) -> None:
        integrity_errors.append(error)
        translate(repository, error)

    def create(name: str) -> str | HTTPException:
        with Session(postgresql_engine) as session:
            try:
                attribute = AtributoService().create(
                    session, {"nombre": name, "tipo_dato": TipoDato.STRING}
                )
                return attribute.codigo
            except HTTPException as error:
                return error

    monkeypatch.setattr(AtributoService, "_validate_unique_code", staticmethod(check))
    monkeypatch.setattr(AtributoRepository, "_raise_integrity", capture)
    sa.event.listen(Atributo, "before_insert", before_insert)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(create, name) for name in names]
            results = [future.result(timeout=20) for future in futures]
    finally:
        sa.event.remove(Atributo, "before_insert", before_insert)

    assert results.count("memoria_ram") == 1
    failures = [result for result in results if isinstance(result, HTTPException)]
    assert len(failures) == 1
    assert failures[0].status_code == 409
    assert isinstance(failures[0].detail, dict)
    assert failures[0].detail["code"] == "ATTRIBUTE_DUPLICATE_CODE"
    assert len(integrity_errors) == 1
    expected_index = NAME_INDEX if names[0] == names[1] else CODE_INDEX
    diagnostic = getattr(integrity_errors[0].orig, "diag", None)
    assert diagnostic is not None
    assert diagnostic.constraint_name == expected_index
    with Session(postgresql_engine) as session:
        assert len(session.exec(select(Atributo)).all()) == 1
        assert len(session.exec(select(AuditLog)).all()) == 1