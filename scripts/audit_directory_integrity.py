from __future__ import annotations

import argparse
import json

from sqlalchemy import create_engine

from osiris.utils.directory_preflight import audit_directory


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preflight de Directorio, solo lectura."
    )
    parser.add_argument(
        "--summary", action="store_true", help="Omitir claves e IDs del reporte."
    )
    parser.add_argument(
        "--host", help="Host de conexion para esta ejecucion, sin cambiar settings."
    )
    parser.add_argument(
        "--port", type=int, help="Puerto publicado para esta ejecucion."
    )
    args = parser.parse_args()
    if args.port is not None and not 1 <= args.port <= 65535:
        parser.error("El puerto debe estar entre 1 y 65535.")

    from osiris.core.db import engine

    audit_engine = (
        create_engine(engine.url.set(host=args.host, port=args.port))
        if args.host or args.port
        else engine
    )
    try:
        with audit_engine.connect() as connection:
            report = audit_directory(connection)
    finally:
        if audit_engine is not engine:
            audit_engine.dispose()
    if args.summary:
        report = {
            "apto_para_migrar": report["apto_para_migrar"],
            "total_conflictos": report["total_conflictos"],
            "conteos": report["conteos"],
            "total_normalizaciones": len(report["requieren_normalizacion"]),
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["apto_para_migrar"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
