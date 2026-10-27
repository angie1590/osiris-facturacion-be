from __future__ import annotations

import json
import importlib.util
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Engine
from sqlmodel import Session

from osiris.core.audit_context import reset_current_user_id, set_current_user_id
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.utils.attribute_code import generate_attribute_code
from osiris.utils.catalog_preflight import audit_catalog
from osiris.utils.catalog_reconciliation import (
    apply_test_attribute_code_reconciliation,
    plan_test_attribute_code_reconciliation,
    plan_test_catalog_reconciliation,
)
from tests.test_catalog_preflight import catalog_engine, snapshot


@pytest.fixture
def attribute_catalog() -> Iterator[tuple[Engine, sa.MetaData]]:
    engine, _ = catalog_engine()
    with engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE tbl_atributo DROP COLUMN codigo")
        connection.exec_driver_sql("ALTER TABLE tbl_atributo ADD COLUMN es_sistema BOOLEAN")
        connection.exec_driver_sql("ALTER TABLE tbl_atributo ADD COLUMN updated_by VARCHAR")
        connection.exec_driver_sql("ALTER TABLE tbl_atributo ADD COLUMN actualizado_en DATETIME")
    metadata = sa.MetaData()
    metadata.reflect(bind=engine)
    sa.Table(
        "tbl_atributo_cambio", metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("snapshot", sa.JSON),
    ).create(engine)
    AuditLog.__table__.create(engine)
    with engine.begin() as connection:
        category_id, product_id = str(uuid4()), str(uuid4())
        connection.execute(metadata.tables["tbl_categoria"].insert().values(
            id=category_id, nombre="Catalogo", activo=True, es_padre=False, is_default=False,
        ))
        connection.execute(metadata.tables["tbl_producto"].insert().values(
            id=product_id, nombre="Producto", activo=True,
        ))
        connection.execute(metadata.tables["tbl_producto_categoria"].insert().values(
            id=str(uuid4()), producto_id=product_id, categoria_id=category_id,
        ))
        for name, active in [("Marca", True), (" Marca ", False), ("MARCA", False),
                             ("DPI", True), ("DPI", False)]:
            attribute_id = str(uuid4())
            connection.execute(metadata.tables["tbl_atributo"].insert().values(
                id=attribute_id, nombre=name, activo=active, tipo_dato="string", es_sistema=False,
            ))
            connection.execute(metadata.tables["tbl_categoria_atributo"].insert().values(
                id=str(uuid4()), categoria_id=category_id, atributo_id=attribute_id,
                activo=active, obligatorio=False,
            ))
            connection.execute(metadata.tables["tbl_producto_atributo_valor"].insert().values(
                id=str(uuid4()), producto_id=product_id, atributo_id=attribute_id,
                activo=active, valor_string="Valor historico",
            ))
            connection.execute(metadata.tables["tbl_atributo_cambio"].insert().values(
                id=str(uuid4()), snapshot={"atributo_id": attribute_id, "nombre": name},
            ))
    token = set_current_user_id("maintenance:authorized-test-data")
    try:
        yield engine, metadata
    finally:
        reset_current_user_id(token)
        engine.dispose()


def test_attribute_reconciliation_preserves_everything_except_inactive_names_and_audit(
    attribute_catalog: tuple[Engine, sa.MetaData],
) -> None:
    engine, metadata = attribute_catalog
    with engine.connect() as connection:
        before = snapshot(connection, metadata)
        plan = plan_test_attribute_code_reconciliation(connection)
        assert plan == plan_test_attribute_code_reconciliation(connection)
        assert snapshot(connection, metadata) == before
        assert len(plan["cambios"]) == 3
        json.dumps(plan)
    with Session(engine) as session, session.begin():
        result = apply_test_attribute_code_reconciliation(
            session, expected_plan_hash=plan["plan_hash"],
        )
        assert result["filas_actualizadas"] == 3
        assert result["apto_para_migrar"] is True
    with engine.connect() as connection:
        after = snapshot(connection, metadata)
        for name in before:
            if name != "tbl_atributo":
                assert before[name] == after[name]
        for previous, current in zip(before["tbl_atributo"], after["tbl_atributo"]):
            assert previous["id"] == current["id"]
            assert previous["activo"] == current["activo"]
            assert previous["tipo_dato"] == current["tipo_dato"]
            if previous["activo"]:
                assert current == previous
            else:
                assert current["nombre"] == (
                    f"{previous['nombre'].strip()} [historico {previous['id']}]"
                )
                assert current["updated_by"] == "maintenance:authorized-test-data"
                assert current["actualizado_en"] is not None
        codes = [generate_attribute_code(row["nombre"]) for row in after["tbl_atributo"]]
        assert len(set(codes)) == len(codes)
        assert audit_catalog(connection)["apto_para_migrar"] is True
        events = connection.execute(sa.select(AuditLog.__table__)).mappings().all()
        assert len(events) == 3
        for event in events:
            assert event["accion"] == "RECONCILE_TEST_ATTRIBUTE"
            assert event["usuario_id"] == "maintenance:authorized-test-data"
            assert event["estado_nuevo"]["plan_hash"] == plan["plan_hash"]
            assert event["estado_anterior"]["codigo_futuro"] in {"marca", "dpi"}
            assert event["estado_nuevo"]["codigo_futuro"] == generate_attribute_code(
                event["estado_nuevo"]["nombre"]
            )
        clean = plan_test_attribute_code_reconciliation(connection)
    with Session(engine) as session, session.begin():
        assert apply_test_attribute_code_reconciliation(
            session, expected_plan_hash=clean["plan_hash"],
        )["filas_actualizadas"] == 0


@pytest.mark.parametrize("table_name, field, value", [
    ("tbl_atributo", "nombre", "Marca diferente"),
    ("tbl_atributo", "tipo_dato", "select"),
    ("tbl_atributo", "activo", True),
    ("tbl_categoria_atributo", "valor_default", "Cambio concurrente"),
    ("tbl_producto_atributo_valor", "valor_string", "Cambio concurrente"),
    ("tbl_atributo_cambio", "snapshot", {"nombre": "Cambio concurrente"}),
])
def test_stale_semantic_state_or_relations_invalidate_hash(
    attribute_catalog: tuple[Engine, sa.MetaData], table_name: str, field: str, value: Any,
) -> None:
    engine, metadata = attribute_catalog
    with engine.connect() as connection:
        plan = plan_test_attribute_code_reconciliation(connection)
    with engine.begin() as connection:
        table = metadata.tables[table_name]
        query = sa.select(table.c.id)
        if table_name == "tbl_atributo":
            query = query.where(table.c.nombre == "MARCA")
        row_id = connection.execute(query.limit(1)).scalar_one()
        connection.execute(table.update().where(table.c.id == row_id).values(**{field: value}))
        before_apply = snapshot(connection, metadata)
    with pytest.raises(RuntimeError):
        with Session(engine) as session, session.begin():
            apply_test_attribute_code_reconciliation(session, expected_plan_hash=plan["plan_hash"])
    with engine.connect() as connection:
        assert snapshot(connection, metadata) == before_apply
        assert connection.execute(sa.select(sa.func.count()).select_from(
            AuditLog.__table__,
        )).scalar_one() == 0


@pytest.mark.parametrize("failure", ["actor", "audit", "hash", "transaction"])
def test_apply_failures_never_leave_partial_changes(
    attribute_catalog: tuple[Engine, sa.MetaData], failure: str,
) -> None:
    engine, metadata = attribute_catalog
    with engine.connect() as connection:
        before = snapshot(connection, metadata)
        plan = plan_test_attribute_code_reconciliation(connection)
    token = set_current_user_id(None if failure == "actor" else "maintenance:authorized-test-data")
    try:
        if failure == "transaction":
            with Session(engine) as session, pytest.raises(RuntimeError, match="transaccion"):
                apply_test_attribute_code_reconciliation(session, expected_plan_hash=plan["plan_hash"])
        else:
            with patch("osiris.utils.catalog_reconciliation.record_domain_change") as audit:
                if failure == "audit":
                    audit.side_effect = RuntimeError("audit failed")
                expected_hash = "stale" if failure == "hash" else plan["plan_hash"]
                with pytest.raises(RuntimeError):
                    with Session(engine) as session, session.begin():
                        apply_test_attribute_code_reconciliation(
                            session, expected_plan_hash=expected_hash,
                        )
                if failure in {"actor", "hash"}:
                    audit.assert_not_called()
    finally:
        reset_current_user_id(token)
    with engine.connect() as connection:
        assert snapshot(connection, metadata) == before
        assert connection.execute(sa.select(sa.func.count()).select_from(
            AuditLog.__table__,
        )).scalar_one() == 0


@pytest.mark.parametrize("failure", ["codigo", "active", "protected", "length", "collision", "category"])
def test_planning_rejects_unsafe_changes(
    attribute_catalog: tuple[Engine, sa.MetaData], failure: str,
) -> None:
    engine, metadata = attribute_catalog
    with engine.begin() as connection:
        table = metadata.tables["tbl_atributo"]
        if failure == "codigo":
            connection.exec_driver_sql("ALTER TABLE tbl_atributo ADD COLUMN codigo VARCHAR")
        elif failure == "active":
            connection.execute(table.update().where(table.c.nombre == "MARCA").values(activo=True))
        elif failure == "protected":
            connection.execute(table.update().where(table.c.nombre == "MARCA").values(es_sistema=True))
        elif failure == "length":
            connection.execute(table.update().where(table.c.nombre.in_(["DPI", "MARCA"])).values(
                nombre="A" * 80,
            ))
        elif failure == "collision":
            row = connection.execute(sa.select(table).where(table.c.nombre == "MARCA")).mappings().one()
            name = f"{row['nombre'].strip()} [historico {row['id']}]"
            connection.execute(table.insert().values(
                id=str(uuid4()), nombre=name, activo=False, tipo_dato="string", es_sistema=False,
            ))
        else:
            category = metadata.tables["tbl_categoria"]
            connection.execute(category.update().values(es_padre=True))
        before = snapshot(connection, metadata) if failure != "codigo" else None
        with pytest.raises((RuntimeError, ValueError)):
            plan_test_attribute_code_reconciliation(connection)
        if before is not None:
            assert snapshot(connection, metadata) == before


def test_all_inactive_group_and_nonliteral_code_collision(
    attribute_catalog: tuple[Engine, sa.MetaData],
) -> None:
    engine, metadata = attribute_catalog
    table = metadata.tables["tbl_atributo"]
    with engine.begin() as connection:
        connection.execute(table.update().where(table.c.nombre == "DPI").values(activo=False))
        connection.execute(table.update().where(table.c.nombre == "MARCA").values(nombre="M\u00e1rca!"))
        plan = plan_test_attribute_code_reconciliation(connection)
        assert len(plan["cambios"]) == 4
    with Session(engine) as session, session.begin():
        assert apply_test_attribute_code_reconciliation(
            session, expected_plan_hash=plan["plan_hash"],
        )["filas_actualizadas"] == 4


def test_new_preflight_generated_conflict_is_supported_only_in_attribute_mode(
    attribute_catalog: tuple[Engine, sa.MetaData],
) -> None:
    engine, _ = attribute_catalog
    with engine.connect() as connection:
        report = audit_catalog(connection)
        report["conflictos"] = [{"code": "ATTRIBUTE_DUPLICATE_CODE", "codigo_previsto": True}]
        report["total_conflictos"] = 1
        report["apto_para_migrar"] = False
        with patch("osiris.utils.catalog_reconciliation.audit_catalog", return_value=report):
            assert len(plan_test_attribute_code_reconciliation(connection)["cambios"]) == 3
            with pytest.raises(RuntimeError, match="ATTRIBUTE_DUPLICATE_CODE"):
                plan_test_catalog_reconciliation(connection)


@pytest.mark.parametrize("apply", [False, True])
def test_cli_selects_attribute_mode_without_writes_by_default(
    attribute_catalog: tuple[Engine, sa.MetaData], monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str], apply: bool,
) -> None:
    engine, metadata = attribute_catalog
    path = Path(__file__).parents[1] / "scripts/reconcile_test_catalog.py"
    spec = importlib.util.spec_from_file_location("attribute_reconciliation_cli", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with engine.connect() as connection:
        before = snapshot(connection, metadata)
        plan = plan_test_attribute_code_reconciliation(connection)
    arguments = [str(path), "--attribute-codes"]
    if apply:
        arguments.extend(["--apply-test-data", "--expected-plan-hash", plan["plan_hash"]])
    monkeypatch.setattr(sys, "argv", arguments)
    monkeypatch.setenv("ENVIRONMENT", "test")
    database_module = ModuleType("osiris.core.db")
    setattr(database_module, "engine", engine)
    monkeypatch.setitem(sys.modules, "osiris.core.db", database_module)
    assert module.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["plan_hash"] == plan["plan_hash"]
    with engine.connect() as connection:
        if apply:
            assert report["filas_actualizadas"] == 3
        else:
            assert snapshot(connection, metadata) == before


@pytest.mark.parametrize("arguments, environment", [
    (["--apply-test-data"], "development"),
    (["--apply-test-data", "--expected-plan-hash", "reviewed"], "production"),
])
def test_cli_attribute_mode_reuses_confirmation_and_environment_guard(
    monkeypatch: pytest.MonkeyPatch, arguments: list[str], environment: str,
) -> None:
    path = Path(__file__).parents[1] / "scripts/reconcile_test_catalog.py"
    spec = importlib.util.spec_from_file_location("attribute_guard_cli", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("ENVIRONMENT", environment)
    monkeypatch.setattr(sys, "argv", [str(path), "--attribute-codes", *arguments])
    with pytest.raises(SystemExit) as error:
        module.main()
    assert error.value.code == 2


def test_postgres_locks_before_reading_or_validating_plan() -> None:
    session = Mock(spec=Session)
    connection = session.connection.return_value
    connection.dialect.name = "postgresql"
    events: list[str] = []
    connection.execute.side_effect = lambda statement: events.append(str(statement))
    with (
        patch("osiris.utils.catalog_reconciliation.acquire_catalog_mutation_lock",
              side_effect=lambda value: events.append("advisory")) as lock,
        patch("osiris.utils.catalog_reconciliation.plan_test_attribute_code_reconciliation",
              side_effect=RuntimeError("stop after lock")) as planner,
        pytest.raises(RuntimeError, match="stop after lock"),
    ):
        apply_test_attribute_code_reconciliation(session, expected_plan_hash="reviewed")
    lock.assert_called_once_with(session)
    planner.assert_called_once_with(connection)
    assert events == ["advisory", "LOCK TABLE tbl_atributo IN SHARE ROW EXCLUSIVE MODE"]


def test_unsupported_database_is_rejected_before_planning() -> None:
    session = Mock(spec=Session)
    session.connection.return_value.dialect.name = "mysql"
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        apply_test_attribute_code_reconciliation(session, expected_plan_hash="reviewed")


def test_code_generation_never_truncates_long_codes(
    attribute_catalog: tuple[Engine, sa.MetaData],
) -> None:
    engine, metadata = attribute_catalog
    with engine.begin() as connection:
        connection.execute(metadata.tables["tbl_atributo"].insert().values(
            id=str(uuid4()), nombre="1" * 120, activo=False, tipo_dato="string", es_sistema=False,
        ))
        with pytest.raises(RuntimeError, match="ATTRIBUTE_CODE_TOO_LONG"):
            plan_test_attribute_code_reconciliation(connection)