from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.engine import Connection
from sqlmodel import Session

from osiris.core.audit import record_domain_change
from osiris.core.audit_context import get_current_user_id
from osiris.core.catalog_lock import acquire_catalog_mutation_lock
from osiris.utils.attribute_code import generate_attribute_code
from osiris.utils.catalog_preflight import audit_catalog


def _attribute_reconciliation_state(
    connection: Connection, table_names: list[str]
) -> dict[str, list[dict[str, Any]]]:
    metadata = sa.MetaData()
    state: dict[str, list[dict[str, Any]]] = {}
    for name in sorted(set(table_names) | {"tbl_atributo"}):
        table = sa.Table(name, metadata, autoload_with=connection)
        state[name] = [
            json.loads(json.dumps(dict(row), default=str, sort_keys=True))
            for row in connection.execute(sa.select(table).order_by(table.c.id)).mappings()
        ]
    return state


def plan_test_attribute_code_reconciliation(connection: Connection) -> dict[str, Any]:
    table = sa.Table("tbl_atributo", sa.MetaData(), autoload_with=connection)
    if "codigo" in table.c:
        raise RuntimeError("La columna codigo ya existe; no se cambia una identidad desplegada.")
    report = audit_catalog(connection)
    unsupported = [
        issue["code"] for issue in report["conflictos"]
        if not (issue["code"] == "ATTRIBUTE_DUPLICATE_CODE" and issue.get("codigo_previsto") is True)
    ]
    if unsupported:
        raise RuntimeError(
            "La conciliacion de atributos no corrige estos conflictos: "
            + ", ".join(sorted(set(unsupported)))
        )
    state = _attribute_reconciliation_state(connection, list(report["conteos"]))
    rows = state["tbl_atributo"]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[generate_attribute_code(row["nombre"])].append(row)
    planned = {row["id"]: dict(row) for row in rows}
    protected_fields = (
        "es_sistema", "is_system", "system_protected", "is_protected", "protegido",
        "es_protegido", "is_default",
    )
    duplicates = [group for group in groups.values() if len(group) > 1]
    for group in duplicates:
        if sum(bool(row["activo"]) for row in group) > 1:
            raise RuntimeError("Existen varios atributos activos con el mismo codigo generado.")
        if any(any(row.get(field) for field in protected_fields) for row in group):
            raise RuntimeError("No se renombran grupos de atributos protegidos de sistema.")
        for row in group:
            if not row["activo"]:
                name = f"{row['nombre'].strip()} [historico {UUID(row['id'])}]"
                if len(name) > 120:
                    raise RuntimeError("El nombre historico propuesto supera 120 caracteres.")
                planned[row["id"]]["nombre"] = name
    codes: set[str] = set()
    active_names: set[str] = set()
    changes: list[dict[str, Any]] = []
    for row in rows:
        target = planned[row["id"]]
        code = generate_attribute_code(target["nombre"])
        if code in codes:
            raise RuntimeError("El nombre historico propuesto tambien genera un codigo duplicado.")
        codes.add(code)
        if target["activo"]:
            name_key = target["nombre"].strip().lower()
            if name_key in active_names:
                raise RuntimeError("Existen nombres de atributos activos duplicados.")
            active_names.add(name_key)
        if target != row:
            changes.append({
                "id": row["id"],
                "antes": {**row, "codigo_futuro": generate_attribute_code(row["nombre"])},
                "despues": {**target, "codigo_futuro": code},
            })
    fingerprint = json.dumps(
        {"estado": state, "cambios": changes}, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True,
    )
    return {
        "version": 1,
        "alcance": "codigos_atributos_pre_e1",
        "solo_datos_prueba": True,
        "plan_hash": hashlib.sha256(fingerprint.encode("utf-8")).hexdigest(),
        "conflictos_antes": report["total_conflictos"],
        "grupos_codigo_duplicado": len(duplicates),
        "cambios": changes,
        "conteos_antes": report["conteos"],
    }


def apply_test_attribute_code_reconciliation(
    session: Session, *, expected_plan_hash: str
) -> dict[str, Any]:
    if not session.in_transaction():
        raise RuntimeError("La conciliacion requiere una transaccion exterior activa.")
    connection = session.connection()
    if connection.dialect.name == "postgresql":
        acquire_catalog_mutation_lock(session)
        connection.execute(sa.text("LOCK TABLE tbl_atributo IN SHARE ROW EXCLUSIVE MODE"))
    elif connection.dialect.name != "sqlite":
        raise RuntimeError(
            "La conciliacion requiere PostgreSQL; SQLite solo se permite para pruebas aisladas."
        )
    plan = plan_test_attribute_code_reconciliation(connection)
    if plan["plan_hash"] != expected_plan_hash:
        raise RuntimeError("El estado del catalogo cambio desde la revision del plan.")
    actor = get_current_user_id()
    if not actor:
        raise RuntimeError("La conciliacion requiere un actor de mantenimiento para auditoria.")
    before = _attribute_reconciliation_state(connection, list(plan["conteos_antes"]))
    table = sa.Table("tbl_atributo", sa.MetaData(), autoload_with=connection)
    ids = {str(row["id"]): row["id"] for row in connection.execute(sa.select(table.c.id)).mappings()}
    for change in plan["cambios"]:
        values: dict[str, Any] = {"nombre": change["despues"]["nombre"]}
        if "actualizado_en" in table.c:
            values["actualizado_en"] = sa.func.now()
        for field in ("updated_by", "usuario_auditoria"):
            if field in table.c:
                values[field] = actor
        connection.execute(table.update().where(table.c.id == ids[change["id"]]).values(**values))
        record_domain_change(
            session,
            entity="tbl_atributo",
            entity_id=UUID(change["id"]),
            action="RECONCILE_TEST_ATTRIBUTE",
            before=change["antes"],
            after={**change["despues"], "plan_hash": plan["plan_hash"]},
            reason="Conciliacion de datos de prueba autorizada por el mantenedor.",
        )
    session.flush()
    after = audit_catalog(connection)
    verified = plan_test_attribute_code_reconciliation(connection)
    current = _attribute_reconciliation_state(connection, list(plan["conteos_antes"]))
    if (
        not after["apto_para_migrar"]
        or verified["cambios"]
        or after["conteos"] != plan["conteos_antes"]
        or any(current[name] != rows for name, rows in before.items() if name != "tbl_atributo")
    ):
        raise RuntimeError("La conciliacion no dejo el catalogo consistente o cambio otras filas.")
    return {
        "plan_hash": plan["plan_hash"],
        "filas_actualizadas": len(plan["cambios"]),
        "apto_para_migrar": after["apto_para_migrar"],
        "conflictos_despues": after["total_conflictos"],
        "conteos": after["conteos"],
    }


def plan_test_catalog_reconciliation(connection: Connection) -> dict[str, Any]:
    report = audit_catalog(connection)
    allowed = {"CATEGORY_DUPLICATE_NAME", "CATEGORY_PARENT_FLAG_MISMATCH"}
    unsupported = [issue["code"] for issue in report["conflictos"] if issue["code"] not in allowed]
    if unsupported:
        raise RuntimeError(
            f"La conciliacion no corrige estos conflictos: {', '.join(sorted(set(unsupported)))}"
        )
    table = sa.Table("tbl_categoria", sa.MetaData(), autoload_with=connection)
    rows = {
        str(row["id"]): {
            "id": str(row["id"]),
            "nombre": row["nombre"],
            "parent_id": str(row["parent_id"]) if row["parent_id"] is not None else None,
            "activo": bool(row["activo"]),
            "es_padre": bool(row["es_padre"]),
            "is_default": bool(row["is_default"]),
        }
        for row in connection.execute(sa.select(table)).mappings()
    }
    planned = {key: dict(row) for key, row in rows.items()}
    for conflict in report["conflictos"]:
        if conflict["code"] == "CATEGORY_DUPLICATE_NAME":
            group = [rows[category_id] for category_id in conflict["ids"]]
            if sum(row["activo"] for row in group) > 1:
                raise RuntimeError(
                    "Existen categorias activas duplicadas; no se elige una identidad arbitrariamente."
                )
            if any(row["is_default"] for row in group):
                raise RuntimeError("No se renombran categorias temporales protegidas.")
            for row in group:
                if not row["activo"]:
                    planned[row["id"]]["nombre"] = (
                        f"{row['nombre'].strip()} [historico {row['id']}]"
                    )
        elif conflict["code"] == "CATEGORY_PARENT_FLAG_MISMATCH":
            for category_id in conflict["ids"]:
                planned[category_id]["es_padre"] = conflict["tiene_hijos"]
    names: set[tuple[str | None, str]] = set()
    for row in planned.values():
        identity = (row["parent_id"], row["nombre"].strip().lower())
        if identity in names:
            raise RuntimeError("El nombre historico propuesto tambien genera un duplicado.")
        names.add(identity)
    changes = [
        {"id": category_id, "antes": rows[category_id], "despues": planned[category_id]}
        for category_id in sorted(rows)
        if planned[category_id] != rows[category_id]
    ]
    fingerprint = json.dumps(
        {"categorias": [rows[key] for key in sorted(rows)], "cambios": changes},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return {
        "version": 1,
        "solo_datos_prueba": True,
        "plan_hash": hashlib.sha256(fingerprint.encode("utf-8")).hexdigest(),
        "conflictos_antes": report["total_conflictos"],
        "cambios": changes,
        "conteos_antes": report["conteos"],
    }


def apply_test_catalog_reconciliation(
    session: Session, *, expected_plan_hash: str
) -> dict[str, Any]:
    if not session.in_transaction():
        raise RuntimeError("La conciliacion requiere una transaccion exterior activa.")
    connection = session.connection()
    if connection.dialect.name == "postgresql":
        acquire_catalog_mutation_lock(session)
        connection.execute(sa.text("LOCK TABLE tbl_categoria IN SHARE ROW EXCLUSIVE MODE"))
    elif connection.dialect.name != "sqlite":
        raise RuntimeError(
            "La conciliacion requiere PostgreSQL; SQLite solo se permite para pruebas aisladas."
        )
    plan = plan_test_catalog_reconciliation(connection)
    if plan["plan_hash"] != expected_plan_hash:
        raise RuntimeError("El estado del catalogo cambio desde la revision del plan.")
    actor = get_current_user_id()
    if plan["cambios"] and not actor:
        raise RuntimeError("La conciliacion requiere un actor de mantenimiento para auditoria.")
    table = sa.Table("tbl_categoria", sa.MetaData(), autoload_with=connection)
    ids = {
        str(row["id"]): row["id"] for row in connection.execute(sa.select(table.c.id)).mappings()
    }
    for change in plan["cambios"]:
        values: dict[str, Any] = {
            "nombre": change["despues"]["nombre"],
            "es_padre": change["despues"]["es_padre"],
        }
        if "actualizado_en" in table.c:
            values["actualizado_en"] = sa.func.now()
        for audit_field in ("updated_by", "usuario_auditoria"):
            if audit_field in table.c:
                values[audit_field] = actor
        connection.execute(table.update().where(table.c.id == ids[change["id"]]).values(**values))
        record_domain_change(
            session,
            entity="tbl_categoria",
            entity_id=UUID(change["id"]),
            action="RECONCILE_TEST_CATEGORY",
            before=change["antes"],
            after={**change["despues"], "plan_hash": plan["plan_hash"]},
            reason="Conciliacion de datos de prueba autorizada por el mantenedor.",
        )
    session.flush()
    after = audit_catalog(connection)
    if not after["apto_para_migrar"] or after["conteos"] != plan["conteos_antes"]:
        raise RuntimeError(
            "La conciliacion no dejo el catalogo consistente o cambio el numero de registros."
        )
    return {
        "plan_hash": plan["plan_hash"],
        "filas_actualizadas": len(plan["cambios"]),
        "apto_para_migrar": after["apto_para_migrar"],
        "conflictos_despues": after["total_conflictos"],
        "conteos": after["conteos"],
    }
