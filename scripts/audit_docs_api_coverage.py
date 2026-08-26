#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


ROUTERS_ROOT = Path("src/osiris/modules")
DOCS_ROOT = Path("docs/docs/api")
METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")


@dataclass(frozen=True)
class Endpoint:
    method: str
    path: str
    source: Path


def _normalize_path(path: str) -> str:
    normalized = path.replace("\\{", "{").replace("\\}", "}")
    normalized = re.sub(r"\{[^}]+\}", "{*}", normalized)
    if normalized.endswith("/") and normalized != "/":
        normalized = normalized[:-1]
    return normalized


def _parse_router_endpoints(router_file: Path) -> list[Endpoint]:
    text = router_file.read_text(encoding="utf-8")

    prefixes: dict[str, str] = {}
    for match in re.finditer(r"(\w+)\s*=\s*APIRouter\(([^)]*)\)", text):
        var_name, args = match.group(1), match.group(2)
        prefix_match = re.search(r'prefix\s*=\s*["\']([^"\']*)["\']', args)
        prefixes[var_name] = prefix_match.group(1) if prefix_match else ""

    endpoints: list[Endpoint] = []
    decorator_pattern = re.compile(
        r'@(\w+)\.(get|post|put|patch|delete)\(\s*["\']([^"\']*)["\']',
        re.IGNORECASE,
    )
    for match in decorator_pattern.finditer(text):
        router_var, method, decorator_path = match.groups()
        method = method.upper()
        prefix = prefixes.get(router_var, "")
        full_path = f"{prefix}{decorator_path}" if decorator_path else prefix
        endpoints.append(
            Endpoint(
                method=method,
                path=_normalize_path(full_path),
                source=router_file,
            )
        )
    return endpoints


def collect_backend_endpoints() -> list[Endpoint]:
    endpoints: list[Endpoint] = []
    for router_file in sorted(ROUTERS_ROOT.rglob("router.py")):
        endpoints.extend(_parse_router_endpoints(router_file))
    return endpoints


def collect_doc_tokens() -> tuple[set[tuple[str, str]], set[str]]:
    method_and_path: set[tuple[str, str]] = set()
    path_only: set[str] = set()

    if not DOCS_ROOT.exists():
        return method_and_path, path_only

    method_path_pattern = re.compile(
        r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/api/v1/[A-Za-z0-9_\-/{}/]+)"
    )
    path_pattern = re.compile(r"/api/v1/[A-Za-z0-9_\-/{}/]+")

    for doc_file in sorted(DOCS_ROOT.rglob("*.md")):
        text = doc_file.read_text(encoding="utf-8")
        text = text.replace("\\{", "{").replace("\\}", "}")

        for match in method_path_pattern.finditer(text):
            method, path = match.groups()
            method_and_path.add((method.upper(), _normalize_path(path)))

        for path in path_pattern.findall(text):
            path_only.add(_normalize_path(path))

    return method_and_path, path_only


def main() -> int:
    backend_endpoints = collect_backend_endpoints()
    doc_method_paths, doc_paths = collect_doc_tokens()

    missing: list[Endpoint] = []
    by_module = Counter()
    for endpoint in backend_endpoints:
        parts = endpoint.source.parts
        module_name = parts[3] if len(parts) > 3 else "unknown"
        by_module[module_name] += 1
        if (endpoint.method, endpoint.path) in doc_method_paths:
            continue
        if endpoint.path in doc_paths:
            continue
        missing.append(endpoint)

    print("== Docs API Coverage Audit ==")
    print(f"Backend endpoints: {len(backend_endpoints)}")
    print("By module:")
    for module_name in sorted(by_module):
        print(f"  - {module_name}: {by_module[module_name]}")

    print(f"Missing in docs: {len(missing)}")
    if missing:
        for endpoint in missing:
            print(
                f"  - {endpoint.method} {endpoint.path} "
                f":: {endpoint.source.as_posix()}"
            )
        return 1

    print("Coverage OK: all backend endpoints are documented in docs/docs/api.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
