from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from unittest.mock import patch
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlmodel import Session

from osiris.core.audit_context import reset_current_user_id, set_current_user_id
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.utils.catalog_preflight import audit_catalog
from osiris.utils.catalog_reconciliation import (
    apply_test_catalog_reconciliation,
    plan_test_catalog_reconciliation,
)
from tests.test_catalog_preflight import catalog_engine, snapshot


@pytest.fixture(autouse=True)
def maintenance_actor():
    token = set_current_user_id("maintenance:authorized-test-data")
    try:
        yield
    finally:
        reset_current_user_id(token)


def seeded_catalog():
    engine, metadata = catalog_engine()
    AuditLog.__table__.create(engine)
    root_id, historical_id, first_id, second_id = [str(uuid4()) for _ in range(4)]
    with engine.begin() as connection:
        connection.execute(
            metadata.tables["tbl_categoria"].insert(),
            [
                {
                    "id": root_id,
                    "nombre": "Tecnologia",
                    "parent_id": None,
                    "activo": True,
                    "es_padre": True,
                    "is_default": False,
                },
                {
                    "id": historical_id,
                    "nombre": " tecnologia ",
                    "parent_id": None,
                    "activo": False,
                    "es_padre": True,
                    "is_default": False,
                },
                {
                    "id": first_id,
                    "nombre": "Teclados",
                    "parent_id": root_id,
                    "activo": False,
                    "es_padre": True,
                    "is_default": False,
                },
                {
                    "id": second_id,
                    "nombre": "Teclados",
                    "parent_id": root_id,
                    "activo": False,
                    "es_padre": False,
                    "is_default": False,
                },
            ],
        )
        product_id, attribute_id = str(uuid4()), str(uuid4())
        connection.execute(
            metadata.tables["tbl_producto"]
            .insert()
            .values(id=product_id, nombre="Producto a conservar", activo=True)
        )
        connection.execute(
            metadata.tables["tbl_producto_categoria"]
            .insert()
            .values(id=str(uuid4()), producto_id=product_id, categoria_id=root_id)
        )
        connection.execute(
            metadata.tables["tbl_atributo"]
            .insert()
            .values(
                id=attribute_id, nombre="Color", codigo="color", tipo_dato="string", activo=True
            )
        )
        connection.execute(
            metadata.tables["tbl_categoria_atributo"]
            .insert()
            .values(
                id=str(uuid4()),
                categoria_id=root_id,
                atributo_id=attribute_id,
                obligatorio=False,
                activo=True,
            )
        )
        connection.execute(
            metadata.tables["tbl_producto_atributo_valor"]
            .insert()
            .values(
                id=str(uuid4()),
                producto_id=product_id,
                atributo_id=attribute_id,
                valor_string="Valor a conservar",
                activo=True,
            )
        )
    return engine, metadata


def test_reconciliation_preserves_rows_references_and_audits_changes():
    engine, metadata = seeded_catalog()
    with engine.connect() as connection:
        before = snapshot(connection, metadata)
        plan = plan_test_catalog_reconciliation(connection)
        assert snapshot(connection, metadata) == before
        assert len(plan["cambios"]) == 4
    actor = set_current_user_id("maintenance:authorized-test-data")
    try:
        with Session(engine) as session, session.begin():
            result = apply_test_catalog_reconciliation(
                session, expected_plan_hash=plan["plan_hash"]
            )
            assert result["apto_para_migrar"] is True
    finally:
        reset_current_user_id(actor)
    with engine.connect() as connection:
        after = snapshot(connection, metadata)
        assert {row["id"] for row in before["tbl_categoria"]} == {
            row["id"] for row in after["tbl_categoria"]
        }
        assert before["tbl_producto"] == after["tbl_producto"]
        assert before["tbl_producto_categoria"] == after["tbl_producto_categoria"]
        assert before["tbl_categoria_atributo"] == after["tbl_categoria_atributo"]
        assert before["tbl_producto_atributo_valor"] == after["tbl_producto_atributo_valor"]
        for row in after["tbl_categoria"]:
            previous = next(item for item in before["tbl_categoria"] if item["id"] == row["id"])
            assert previous["parent_id"] == row["parent_id"]
            assert previous["activo"] == row["activo"]
            if previous["activo"]:
                assert row["nombre"] == previous["nombre"]
        assert audit_catalog(connection)["apto_para_migrar"] is True
        audit = AuditLog.__table__
        events = connection.execute(sa.select(audit)).mappings().all()
        assert len(events) == 4
        assert {event["accion"] for event in events} == {"RECONCILE_TEST_CATEGORY"}
        assert {event["usuario_id"] for event in events} == {"maintenance:authorized-test-data"}
        assert plan_test_catalog_reconciliation(connection)["cambios"] == []


def test_reconciliation_rejects_stale_plan_and_rolls_back():
    engine, metadata = seeded_catalog()
    with engine.connect() as connection:
        plan = plan_test_catalog_reconciliation(connection)
    with engine.begin() as connection:
        connection.execute(
            metadata.tables["tbl_categoria"]
            .update()
            .where(metadata.tables["tbl_categoria"].c.activo.is_(True))
            .values(nombre="Cambio concurrente")
        )
    with pytest.raises(RuntimeError, match="cambio"):
        with Session(engine) as session, session.begin():
            apply_test_catalog_reconciliation(session, expected_plan_hash=plan["plan_hash"])
    with engine.connect() as connection:
        assert (
            connection.execute(
                sa.select(sa.func.count()).select_from(AuditLog.__table__)
            ).scalar_one()
            == 0
        )


def test_audit_failure_rolls_back_every_category_change():
    engine, metadata = seeded_catalog()
    with engine.connect() as connection:
        before = snapshot(connection, metadata)
        plan = plan_test_catalog_reconciliation(connection)
    with patch(
        "osiris.utils.catalog_reconciliation.record_domain_change",
        side_effect=RuntimeError("audit failed"),
    ):
        with pytest.raises(RuntimeError, match="audit failed"):
            with Session(engine) as session, session.begin():
                apply_test_catalog_reconciliation(session, expected_plan_hash=plan["plan_hash"])
    with engine.connect() as connection:
        assert snapshot(connection, metadata) == before


def test_multiple_active_duplicates_are_not_arbitrarily_chosen():
    engine, metadata = seeded_catalog()
    with engine.begin() as connection:
        table = metadata.tables["tbl_categoria"]
        connection.execute(table.update().where(table.c.parent_id.is_(None)).values(activo=True))
        with pytest.raises(RuntimeError, match="activas"):
            plan_test_catalog_reconciliation(connection)


def test_reconciliation_does_not_write_without_audit_actor():
    engine, metadata = seeded_catalog()
    with engine.connect() as connection:
        before = snapshot(connection, metadata)
        plan = plan_test_catalog_reconciliation(connection)
    token = set_current_user_id(None)
    try:
        with pytest.raises(RuntimeError, match="actor de mantenimiento"):
            with Session(engine) as session, session.begin():
                apply_test_catalog_reconciliation(session, expected_plan_hash=plan["plan_hash"])
    finally:
        reset_current_user_id(token)
    with engine.connect() as connection:
        assert snapshot(connection, metadata) == before


@pytest.mark.parametrize("arguments, environment", [
    (["--apply-test-data"], "development"),
    (["--apply-test-data", "--expected-plan-hash", "reviewed"], "production"),
])
def test_cli_rejects_unconfirmed_or_production_apply(monkeypatch, arguments, environment):
    script_path = Path(__file__).parents[1] / "scripts/reconcile_test_catalog.py"
    spec = importlib.util.spec_from_file_location("catalog_reconciliation_cli", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("ENVIRONMENT", environment)
    monkeypatch.setattr(sys, "argv", [str(script_path), *arguments])
    with pytest.raises(SystemExit) as error:
        module.main()
    assert error.value.code == 2
