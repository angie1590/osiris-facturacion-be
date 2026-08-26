from __future__ import annotations

from sqlmodel import create_engine

from osiris.core.db import attach_engine_observability
from osiris.core.observability import (
    begin_db_request_tracking,
    get_current_db_request_stats,
    record_db_query,
    reset_db_request_tracking,
)


def _parse_metric_value(
    metrics_text: str,
    *,
    name: str,
    labels: dict[str, str],
) -> float:
    expected = tuple(sorted(labels.items()))
    for raw_line in metrics_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or not line.startswith(name):
            continue

        metric_and_value = line.split(" ", 1)
        if len(metric_and_value) != 2:
            continue

        metric_part, value_part = metric_and_value
        if "{" not in metric_part or not metric_part.endswith("}"):
            continue

        _, raw_labels = metric_part.split("{", 1)
        raw_labels = raw_labels[:-1]  # strip trailing "}"
        parsed_labels: list[tuple[str, str]] = []
        for pair in raw_labels.split(","):
            if "=" not in pair:
                continue
            key, value = pair.split("=", 1)
            parsed_labels.append((key, value.strip('"')))

        if tuple(sorted(parsed_labels)) != expected:
            continue
        return float(value_part)
    return 0.0


def test_record_db_query_updates_per_request_stats():
    token = begin_db_request_tracking()
    try:
        record_db_query(
            statement="SELECT 1",
            duration_seconds=0.01,
            slow_query_threshold_seconds=0.005,
        )
        stats = get_current_db_request_stats()
        assert stats.query_count == 1
        assert stats.slow_query_count == 1
        assert stats.total_time_seconds >= 0.01
    finally:
        reset_db_request_tracking(token)


def test_attach_engine_observability_collects_select_query_metrics():
    engine = create_engine("sqlite://")
    attach_engine_observability(engine, slow_query_threshold_ms=1000)

    before_text = ""
    from osiris.core.observability import METRICS

    before_text = METRICS.render_prometheus()
    before = _parse_metric_value(
        before_text,
        name="osiris_db_queries_total",
        labels={"statement_type": "SELECT"},
    )

    with engine.connect() as connection:
        connection.exec_driver_sql("SELECT 1")

    after_text = METRICS.render_prometheus()
    after = _parse_metric_value(
        after_text,
        name="osiris_db_queries_total",
        labels={"statement_type": "SELECT"},
    )
    assert after >= before + 1
