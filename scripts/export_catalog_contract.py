"""Export the NOT DEPLOYED schema fixture, without importing the runtime app."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from osiris.domain.catalog_contracts import create_contract_app


DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1] / "contracts" / "catalog-administration-v1.openapi.json"
)


def render_contract() -> str:
    return json.dumps(create_contract_app().openapi(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Verify snapshot without writing.")
    args = parser.parse_args()
    expected = render_contract()
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != expected:
            print(f"Contract snapshot missing or stale: {args.output}")
            return 1
        print(f"Contract snapshot matches: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8")
    print(f"NOT DEPLOYED contract exported: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())