from __future__ import annotations

import argparse
import json
import os

import sqlalchemy as sa
from sqlmodel import Session

from osiris.core.audit_context import reset_current_user_id, set_current_user_id
from osiris.utils.catalog_reconciliation import (
    apply_test_attribute_code_reconciliation,
    apply_test_catalog_reconciliation,
    plan_test_attribute_code_reconciliation,
    plan_test_catalog_reconciliation,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Conciliacion explicita de catalogo de prueba. Sin --apply-test-data solo lee."
    )
    parser.add_argument(
        "--attribute-codes", action="store_true",
        help="Conciliar nombres historicos de atributos antes de desplegar codigo (pre-e1).",
    )
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument(
        "--apply-test-data",
        action="store_true",
        help="Aplicar unicamente renombres historicos y flags padre en datos de prueba autorizados.",
    )
    parser.add_argument(
        "--expected-plan-hash", help="Hash exacto del plan revisado; obligatorio al aplicar."
    )
    args = parser.parse_args()
    planner = (
        plan_test_attribute_code_reconciliation
        if args.attribute_codes else plan_test_catalog_reconciliation
    )
    applier = (
        apply_test_attribute_code_reconciliation
        if args.attribute_codes else apply_test_catalog_reconciliation
    )
    if args.port is not None and not 1 <= args.port <= 65535:
        parser.error("El puerto debe estar entre 1 y 65535.")
    if args.apply_test_data and not args.expected_plan_hash:
        parser.error("Para aplicar debes indicar --expected-plan-hash del plan revisado.")
    if args.apply_test_data and os.getenv("ENVIRONMENT", "development").lower() not in {
        "development",
        "test",
        "testing",
    }:
        parser.error("La conciliacion de prueba solo permite entornos development/test.")

    from osiris.core.db import engine

    reconciliation_engine = (
        sa.create_engine(engine.url.set(host=args.host, port=args.port))
        if args.host or args.port
        else engine
    )
    try:
        if args.apply_test_data:
            actor_token = set_current_user_id("maintenance:catalog-test-reconciliation")
            try:
                with Session(reconciliation_engine) as session, session.begin():
                    report = applier(
                        session, expected_plan_hash=args.expected_plan_hash
                    )
            finally:
                reset_current_user_id(actor_token)
        else:
            with reconciliation_engine.connect() as connection:
                if connection.dialect.name == "postgresql":
                    connection = connection.execution_options(isolation_level="REPEATABLE READ")
                with connection.begin():
                    if connection.dialect.name == "postgresql":
                        connection.execute(sa.text("SET TRANSACTION READ ONLY"))
                    report = planner(connection)
    finally:
        if reconciliation_engine is not engine:
            reconciliation_engine.dispose()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
