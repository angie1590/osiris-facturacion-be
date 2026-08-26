#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

import httpx


DEFAULT_PATHS = (
    "/health/live",
    "/health/ready",
    "/openapi.json",
)


@dataclass(frozen=True)
class Sample:
    path: str
    status_code: int
    latency_ms: float
    ok: bool


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    values_sorted = sorted(values)
    position = (len(values_sorted) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(values_sorted) - 1)
    weight = position - lower
    return values_sorted[lower] * (1 - weight) + values_sorted[upper] * weight


async def _request_once(client: httpx.AsyncClient, path: str) -> Sample:
    started = time.perf_counter()
    try:
        response = await client.get(path)
        latency_ms = (time.perf_counter() - started) * 1000
        ok = 200 <= response.status_code < 300
        return Sample(path=path, status_code=response.status_code, latency_ms=latency_ms, ok=ok)
    except Exception:
        latency_ms = (time.perf_counter() - started) * 1000
        return Sample(path=path, status_code=0, latency_ms=latency_ms, ok=False)


async def _run_load(
    *,
    base_url: str,
    total_requests: int,
    concurrency: int,
    paths: Iterable[str],
    timeout_seconds: float,
) -> list[Sample]:
    normalized_paths = [p if p.startswith("/") else f"/{p}" for p in paths]
    semaphore = asyncio.Semaphore(concurrency)
    samples: list[Sample] = []

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout_seconds) as client:
        async def worker(i: int) -> None:
            path = normalized_paths[i % len(normalized_paths)]
            async with semaphore:
                samples.append(await _request_once(client, path))

        await asyncio.gather(*(worker(i) for i in range(total_requests)))

    return samples


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Smoke de performance para endpoints básicos del backend."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="URL base del API")
    parser.add_argument("--requests", type=int, default=120, help="Total de requests")
    parser.add_argument("--concurrency", type=int, default=20, help="Concurrencia")
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=10.0,
        help="Timeout por request en segundos",
    )
    parser.add_argument(
        "--p95-ms-threshold",
        type=float,
        default=700.0,
        help="Umbral máximo permitido de p95 en milisegundos",
    )
    parser.add_argument(
        "--paths",
        nargs="*",
        default=list(DEFAULT_PATHS),
        help="Rutas a testear (por defecto: /health/live /health/ready /openapi.json)",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.requests <= 0:
        parser.error("--requests debe ser mayor a 0")
    if args.concurrency <= 0:
        parser.error("--concurrency debe ser mayor a 0")

    samples = asyncio.run(
        _run_load(
            base_url=args.base_url.rstrip("/"),
            total_requests=args.requests,
            concurrency=args.concurrency,
            paths=args.paths,
            timeout_seconds=args.timeout_seconds,
        )
    )

    if not samples:
        print("ERROR: no se recolectaron muestras.")
        return 1

    latencies = [sample.latency_ms for sample in samples]
    failures = [sample for sample in samples if not sample.ok]
    by_status = Counter(sample.status_code for sample in samples)
    by_path = Counter(sample.path for sample in samples)
    p50 = _percentile(latencies, 0.50)
    p95 = _percentile(latencies, 0.95)
    p99 = _percentile(latencies, 0.99)
    avg = statistics.mean(latencies)

    print("=== PERF SMOKE RESULT ===")
    print(f"Base URL      : {args.base_url}")
    print(f"Requests      : {len(samples)}")
    print(f"Concurrency   : {args.concurrency}")
    print(f"Paths         : {dict(by_path)}")
    print(f"Status counts : {dict(sorted(by_status.items()))}")
    print(f"Latency avg   : {avg:.2f} ms")
    print(f"Latency p50   : {p50:.2f} ms")
    print(f"Latency p95   : {p95:.2f} ms")
    print(f"Latency p99   : {p99:.2f} ms")
    print(f"Failures      : {len(failures)}")

    if failures:
        print("ERROR: se detectaron respuestas no exitosas.")
        return 2
    if p95 > args.p95_ms_threshold:
        print(
            f"ERROR: p95 ({p95:.2f} ms) excede el umbral permitido "
            f"({args.p95_ms_threshold:.2f} ms)."
        )
        return 3

    print("OK: smoke de performance en verde.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
