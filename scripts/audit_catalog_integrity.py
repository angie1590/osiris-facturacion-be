from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import sqlalchemy as sa

from osiris.utils.catalog_preflight import audit_catalog


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight del catalogo global, solo lectura.")
    parser.add_argument(
        "--summary", action="store_true", help="Omitir nombres, claves e IDs del reporte."
    )
    parser.add_argument(
        "--host", help="Host de conexion para esta ejecucion, sin cambiar settings."
    )
    parser.add_argument("--port", type=int, help="Puerto publicado para esta ejecucion.")
    parser.add_argument(
        "--unit-candidates",
        type=Path,
        help="JSON explicito atributo_id -> unidad_codigo; no asigna ni infiere unidades.",
    )
    args = parser.parse_args()
    if args.port is not None and not 1 <= args.port <= 65535:
        parser.error("El puerto debe estar entre 1 y 65535.")
    unit_candidates: dict[str, str] = {}
    if args.unit_candidates is not None:
        try:
            candidates: Any = json.loads(args.unit_candidates.read_text(encoding="utf-8"))
            if not isinstance(candidates, dict) or any(
                not isinstance(key, str) or not isinstance(value, str)
                for key, value in candidates.items()
            ):
                parser.error(
                    "Los candidatos deben ser un objeto JSON atributo_id -> unidad_codigo."
                )
            unit_candidates = candidates
        except (OSError, ValueError) as exc:
            parser.error(f"No se pudo leer el archivo de candidatos: {exc}")

    from osiris.core.db import engine

    audit_engine = (
        sa.create_engine(engine.url.set(host=args.host, port=args.port))
        if args.host or args.port
        else engine
    )
    try:
        with audit_engine.connect() as connection:
            if connection.dialect.name == "postgresql":
                connection = connection.execution_options(isolation_level="REPEATABLE READ")
            with connection.begin():
                if connection.dialect.name == "postgresql":
                    connection.execute(sa.text("SET TRANSACTION READ ONLY"))
                report = audit_catalog(connection, unit_candidates=unit_candidates)
    finally:
        if audit_engine is not engine:
            audit_engine.dispose()
    if args.summary:
        issue_counts: dict[str, int] = {}
        for conflict in report["conflictos"]:
            code = conflict["code"]
            issue_counts[code] = issue_counts.get(code, 0) + 1
        report = {
            "version": report["version"],
            "alcance": report["alcance"],
            "apto_para_migrar": report["apto_para_migrar"],
            "total_conflictos": report["total_conflictos"],
            "conteos": report["conteos"],
            "conflictos_por_codigo": dict(sorted(issue_counts.items())),
            "total_candidatos_anotacion": len(report["candidatos_anotacion_unidad"]),
            "advertencias": report["advertencias"],
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["apto_para_migrar"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
