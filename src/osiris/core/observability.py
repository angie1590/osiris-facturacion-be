from __future__ import annotations

import json
import logging
import threading
import time
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from osiris.core.audit_context import get_current_company_id, get_current_user_id

_current_request_id: ContextVar[Optional[str]] = ContextVar("current_request_id", default=None)
_current_db_request_stats: ContextVar[Optional["DBRequestStats"]] = ContextVar(
    "current_db_request_stats",
    default=None,
)


@dataclass
class DBRequestStats:
    query_count: int = 0
    total_time_seconds: float = 0.0
    slow_query_count: int = 0


def new_request_id() -> str:
    return str(uuid4())


def set_current_request_id(request_id: str | None) -> Token:
    return _current_request_id.set(request_id)


def reset_current_request_id(token: Token) -> None:
    _current_request_id.reset(token)


def get_current_request_id() -> str | None:
    return _current_request_id.get()


class _ContextLoggingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = get_current_request_id()
        if not hasattr(record, "user_id"):
            record.user_id = get_current_user_id()
        if not hasattr(record, "company_id"):
            record.company_id = get_current_company_id()
        return True


class _JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "user_id": getattr(record, "user_id", None),
            "company_id": getattr(record, "company_id", None),
            "method": getattr(record, "method", None),
            "path": getattr(record, "path", None),
            "status_code": getattr(record, "status_code", None),
            "latency_ms": getattr(record, "latency_ms", None),
            "client_ip": getattr(record, "client_ip", None),
            "db_query_count": getattr(record, "db_query_count", None),
            "db_query_time_ms": getattr(record, "db_query_time_ms", None),
            "db_slow_query_count": getattr(record, "db_slow_query_count", None),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


_LOGGING_CONFIGURED = False


def configure_json_logging(*, level: int = logging.INFO) -> None:
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    logger = logging.getLogger("osiris")
    logger.setLevel(level)
    logger.propagate = False

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(_JsonLogFormatter())
    stream_handler.addFilter(_ContextLoggingFilter())

    logger.handlers.clear()
    logger.addHandler(stream_handler)
    _LOGGING_CONFIGURED = True


def _labels_to_key(labels: dict[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((k, str(v)) for k, v in labels.items()))


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


class _MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, dict[tuple[tuple[str, str], ...], float]] = {}
        self._gauges: dict[str, dict[tuple[tuple[str, str], ...], float]] = {}
        self._histograms: dict[str, dict[tuple[tuple[str, str], ...], tuple[float, int]]] = {}

    def inc_counter(self, name: str, *, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        key = _labels_to_key(labels or {})
        with self._lock:
            series = self._counters.setdefault(name, {})
            series[key] = series.get(key, 0.0) + value

    def observe_histogram(self, name: str, *, value: float, labels: dict[str, str] | None = None) -> None:
        key = _labels_to_key(labels or {})
        with self._lock:
            series = self._histograms.setdefault(name, {})
            current_sum, current_count = series.get(key, (0.0, 0))
            series[key] = (current_sum + value, current_count + 1)

    def set_gauge(self, name: str, *, value: float, labels: dict[str, str] | None = None) -> None:
        key = _labels_to_key(labels or {})
        with self._lock:
            series = self._gauges.setdefault(name, {})
            series[key] = value

    def add_gauge(self, name: str, *, delta: float, labels: dict[str, str] | None = None) -> float:
        key = _labels_to_key(labels or {})
        with self._lock:
            series = self._gauges.setdefault(name, {})
            current = series.get(key, 0.0)
            next_value = current + delta
            series[key] = next_value
            return next_value

    def get_gauge(self, name: str, *, labels: dict[str, str] | None = None) -> float:
        key = _labels_to_key(labels or {})
        with self._lock:
            series = self._gauges.get(name, {})
            return series.get(key, 0.0)

    def render_prometheus(self) -> str:
        lines: list[str] = []
        with self._lock:
            counters = dict(self._counters)
            histograms = dict(self._histograms)
            gauges = dict(self._gauges)

        for name, series in sorted(counters.items()):
            lines.append(f"# TYPE {name} counter")
            for label_key, value in sorted(series.items()):
                lines.append(f"{name}{_render_labels(label_key)} {value}")

        for name, series in sorted(gauges.items()):
            lines.append(f"# TYPE {name} gauge")
            for label_key, value in sorted(series.items()):
                lines.append(f"{name}{_render_labels(label_key)} {value}")

        for name, series in sorted(histograms.items()):
            lines.append(f"# TYPE {name}_sum counter")
            lines.append(f"# TYPE {name}_count counter")
            for label_key, (sum_value, count_value) in sorted(series.items()):
                labels = _render_labels(label_key)
                lines.append(f"{name}_sum{labels} {sum_value}")
                lines.append(f"{name}_count{labels} {count_value}")

        return "\n".join(lines) + "\n"


def _render_labels(label_key: tuple[tuple[str, str], ...]) -> str:
    if not label_key:
        return ""
    pairs = [f'{name}="{_escape_label(value)}"' for name, value in label_key]
    return "{" + ",".join(pairs) + "}"


METRICS = _MetricsRegistry()


def initialize_metrics() -> None:
    # Ensure key series are always present for scraping and QA checks.
    METRICS.set_gauge("osiris_http_in_flight_requests", value=0)
    METRICS.inc_counter("osiris_fe_worker_runs_total", value=0)
    METRICS.inc_counter("osiris_fe_worker_processed_documents_total", value=0)
    METRICS.inc_counter("osiris_fe_worker_errors_total", value=0)
    for reason in ("missing_user", "insufficient_permissions", "endpoint_returned_403"):
        METRICS.inc_counter(
            "osiris_security_unauthorized_access_total",
            value=0,
            labels={"reason": reason},
        )
    METRICS.inc_counter(
        "osiris_db_queries_total",
        value=0,
        labels={"statement_type": "SELECT"},
    )
    METRICS.inc_counter(
        "osiris_db_slow_queries_total",
        value=0,
        labels={"statement_type": "SELECT"},
    )
    METRICS.inc_counter(
        "osiris_http_requests_with_slow_db_queries_total",
        value=0,
        labels={"method": "UNKNOWN", "path": "UNKNOWN"},
    )
    METRICS.inc_counter(
        "osiris_http_overload_rejections_total",
        value=0,
        labels={"method": "UNKNOWN", "path": "UNKNOWN"},
    )
    for status in ("up", "down"):
        METRICS.inc_counter(
            "osiris_health_readiness_checks_total",
            value=0,
            labels={"status": status},
        )


def begin_db_request_tracking() -> Token:
    return _current_db_request_stats.set(DBRequestStats())


def reset_db_request_tracking(token: Token) -> None:
    _current_db_request_stats.reset(token)


def get_current_db_request_stats() -> DBRequestStats:
    current = _current_db_request_stats.get()
    if current is None:
        return DBRequestStats()
    return DBRequestStats(
        query_count=current.query_count,
        total_time_seconds=current.total_time_seconds,
        slow_query_count=current.slow_query_count,
    )


def _resolve_statement_type(statement: str) -> str:
    normalized = statement.strip().split(maxsplit=1)
    if not normalized:
        return "UNKNOWN"
    return normalized[0].upper()


def record_db_query(
    *,
    statement: str,
    duration_seconds: float,
    slow_query_threshold_seconds: float,
) -> None:
    safe_duration = max(duration_seconds, 0.0)
    statement_type = _resolve_statement_type(statement)

    METRICS.inc_counter(
        "osiris_db_queries_total",
        labels={"statement_type": statement_type},
    )
    METRICS.observe_histogram(
        "osiris_db_query_duration_seconds",
        value=safe_duration,
        labels={"statement_type": statement_type},
    )

    is_slow = safe_duration >= max(slow_query_threshold_seconds, 0.0)
    if is_slow:
        METRICS.inc_counter(
            "osiris_db_slow_queries_total",
            labels={"statement_type": statement_type},
        )

    stats = _current_db_request_stats.get()
    if stats is None:
        return
    stats.query_count += 1
    stats.total_time_seconds += safe_duration
    if is_slow:
        stats.slow_query_count += 1


def record_db_request_summary(*, method: str, path: str, stats: DBRequestStats) -> None:
    labels = {"method": method, "path": path}
    METRICS.observe_histogram(
        "osiris_http_db_queries_per_request",
        value=float(max(stats.query_count, 0)),
        labels=labels,
    )
    METRICS.observe_histogram(
        "osiris_http_db_time_seconds_per_request",
        value=max(stats.total_time_seconds, 0.0),
        labels=labels,
    )
    if stats.slow_query_count > 0:
        METRICS.inc_counter(
            "osiris_http_requests_with_slow_db_queries_total",
            labels=labels,
        )


def record_http_overload_rejection(*, method: str, path: str) -> None:
    METRICS.inc_counter(
        "osiris_http_overload_rejections_total",
        labels={"method": method, "path": path},
    )


def record_readiness_check(*, status: str) -> None:
    METRICS.inc_counter(
        "osiris_health_readiness_checks_total",
        labels={"status": status},
    )


def record_http_request(*, method: str, path: str, status_code: int, latency_seconds: float) -> None:
    labels = {"method": method, "path": path, "status_code": str(status_code)}
    METRICS.inc_counter("osiris_http_requests_total", labels=labels)
    METRICS.observe_histogram(
        "osiris_http_request_duration_seconds",
        value=max(latency_seconds, 0.0),
        labels={"method": method, "path": path},
    )


def record_http_in_flight(delta: int) -> None:
    current = METRICS.add_gauge("osiris_http_in_flight_requests", delta=float(delta))
    if current < 0:
        METRICS.set_gauge("osiris_http_in_flight_requests", value=0)


def get_http_in_flight() -> int:
    return int(METRICS.get_gauge("osiris_http_in_flight_requests"))


def record_fe_worker_run(*, processed: int) -> None:
    METRICS.inc_counter("osiris_fe_worker_runs_total")
    if processed > 0:
        METRICS.inc_counter("osiris_fe_worker_processed_documents_total", value=float(processed))


def record_fe_worker_error() -> None:
    METRICS.inc_counter("osiris_fe_worker_errors_total")


def record_unauthorized_access(reason: str) -> None:
    METRICS.inc_counter(
        "osiris_security_unauthorized_access_total",
        labels={"reason": reason},
    )


def observe_request_latency_seconds(start_monotonic: float) -> float:
    return time.monotonic() - start_monotonic
