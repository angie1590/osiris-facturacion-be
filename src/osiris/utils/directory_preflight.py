from __future__ import annotations

from collections import defaultdict
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Connection

DIRECTORY_KEYS = {
    "tbl_persona": "identificacion",
    "tbl_cliente": "persona_id",
    "tbl_proveedor_persona": "persona_id",
    "tbl_empleado": "persona_id",
    "tbl_usuario": "username",
    "tbl_tipo_cliente": "nombre",
    "tbl_proveedor_sociedad": "ruc",
}


def audit_directory(connection: Connection) -> dict[str, Any]:
    metadata = sa.MetaData()
    tables = {
        name: sa.Table(name, metadata, autoload_with=connection)
        for name in DIRECTORY_KEYS
    }
    rows_by_table = {
        name: [dict(row) for row in connection.execute(sa.select(table)).mappings()]
        for name, table in tables.items()
    }
    foreign_keys = sa.inspect(connection).get_multi_foreign_keys()
    conflicts: list[dict[str, Any]] = []
    pending_normalization: list[dict[str, str]] = []
    for table_name, rows in rows_by_table.items():
        keys = [DIRECTORY_KEYS[table_name]]
        if table_name == "tbl_usuario":
            keys.append("persona_id")
        for field in keys:
            groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in rows:
                original = str(row[field])
                normalized = original.strip()
                if field in {"username", "nombre"}:
                    normalized = normalized.lower()
                elif field == "identificacion":
                    normalized = normalized.upper()
                groups[normalized].append(row)
                if original != normalized:
                    pending_normalization.append(
                        {
                            "tabla": table_name,
                            "campo": field,
                            "id": str(row["id"]),
                        }
                    )
            for key, duplicates in sorted(groups.items()):
                if len(duplicates) < 2:
                    continue
                ids = {str(row["id"]) for row in duplicates}
                references: list[dict[str, Any]] = []
                reference_field = None
                if table_name == "tbl_persona":
                    reference_field = "persona_id"
                elif table_name == "tbl_tipo_cliente":
                    reference_field = "tipo_cliente_id"
                if reference_field:
                    for related_name, related_rows in rows_by_table.items():
                        related_field = reference_field
                        if (
                            table_name == "tbl_persona"
                            and related_name == "tbl_proveedor_sociedad"
                        ):
                            related_field = "persona_contacto_id"
                        for related in related_rows:
                            if str(related.get(related_field)) in ids:
                                references.append(
                                    {
                                        "tabla": related_name,
                                        "id": str(related["id"]),
                                        "activo": bool(related["activo"]),
                                    }
                                )
                seen_references = {(item["tabla"], item["id"]) for item in references}
                for (schema, related_name), constraints in foreign_keys.items():
                    for constraint in constraints:
                        if constraint["referred_table"] != table_name or constraint[
                            "referred_columns"
                        ] != ["id"]:
                            continue
                        related_table = sa.Table(
                            related_name,
                            metadata,
                            schema=schema,
                            autoload_with=connection,
                        )
                        related_field = constraint["constrained_columns"][0]
                        referenced_results = connection.execute(
                            sa.select(related_table).where(
                                sa.cast(
                                    related_table.c[related_field], sa.String()
                                ).in_(ids)
                            )
                        ).mappings()
                        for reference_row in referenced_results:
                            related_id = (
                                str(reference_row.get("id"))
                                if "id" in reference_row
                                else ",".join(
                                    f"{column.name}={reference_row[column.name]}"
                                    for column in related_table.primary_key
                                )
                            )
                            if (related_name, related_id) not in seen_references:
                                references.append(
                                    {
                                        "tabla": related_name,
                                        "id": related_id,
                                        "activo": reference_row.get("activo"),
                                    }
                                )
                                seen_references.add((related_name, related_id))
                conflicts.append(
                    {
                        "tabla": table_name,
                        "campo": field,
                        "clave_normalizada": key,
                        "registros": [
                            {"id": str(row["id"]), "activo": bool(row["activo"])}
                            for row in duplicates
                        ],
                        "referencias_directorio": references,
                        "referencias_historicas": references,
                    }
                )
    return {
        "apto_para_migrar": not conflicts,
        "total_conflictos": len(conflicts),
        "conflictos": conflicts,
        "requieren_normalizacion": pending_normalization,
        "conteos": {name: len(rows) for name, rows in rows_by_table.items()},
    }


def require_clean_directory(connection: Connection) -> None:
    report = audit_directory(connection)
    if not report["apto_para_migrar"]:
        summary = ", ".join(
            f"{conflict['tabla']}.{conflict['campo']}"
            for conflict in report["conflictos"]
        )
        raise RuntimeError(
            "Directorio contiene duplicados normalizados: "
            f"{summary}. Ejecutar scripts/audit_directory_integrity.py y resolver "
            "las referencias con aprobacion administrativa antes de migrar."
        )
