from __future__ import annotations

import time
from typing import Generator

from sqlalchemy import event, true
from sqlalchemy.engine import Engine
from sqlalchemy.orm import with_loader_criteria
from sqlmodel import Session, SQLModel, create_engine

from osiris.core.observability import record_db_query
from osiris.core.settings import get_settings
from osiris.domain.base_models import SoftDeleteMixin


SOFT_DELETE_INCLUDE_INACTIVE_OPTION = "include_inactive"


def get_engine():
    settings = get_settings()
    db_engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.SQL_ECHO,
        pool_pre_ping=True,
    )
    if settings.OBSERVABILITY_METRICS_ENABLED and settings.OBSERVABILITY_DB_METRICS_ENABLED:
        attach_engine_observability(
            db_engine,
            slow_query_threshold_ms=settings.OBSERVABILITY_DB_SLOW_QUERY_THRESHOLD_MS,
        )
    return db_engine


def attach_engine_observability(db_engine: Engine, *, slow_query_threshold_ms: int) -> None:
    if getattr(db_engine, "_osiris_observability_attached", False):
        return

    slow_query_threshold_seconds = max(float(slow_query_threshold_ms), 1.0) / 1000.0
    query_time_stack_key = "_osiris_query_start_times"

    @event.listens_for(db_engine, "before_cursor_execute")
    def _before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany  # noqa: ANN001, ARG001
    ):
        _ = (cursor, statement, parameters, context, executemany)
        query_times = conn.info.setdefault(query_time_stack_key, [])
        query_times.append(time.perf_counter())

    @event.listens_for(db_engine, "after_cursor_execute")
    def _after_cursor_execute(
        conn, cursor, statement, parameters, context, executemany  # noqa: ANN001, ARG001
    ):
        _ = (cursor, parameters, context, executemany)
        query_times = conn.info.get(query_time_stack_key) or []
        if not query_times:
            return
        started_at = query_times.pop()
        duration_seconds = time.perf_counter() - started_at
        record_db_query(
            statement=statement,
            duration_seconds=duration_seconds,
            slow_query_threshold_seconds=slow_query_threshold_seconds,
        )

    @event.listens_for(db_engine, "handle_error")
    def _handle_error(exception_context):  # noqa: ANN001
        connection = getattr(exception_context, "connection", None)
        if connection is None:
            return
        query_times = connection.info.get(query_time_stack_key) or []
        if query_times:
            query_times.pop()

    setattr(db_engine, "_osiris_observability_attached", True)


# Engine global practico para imports
engine = get_engine()


@event.listens_for(Session, "do_orm_execute")
def _apply_soft_delete_filter(execute_state):
    if not execute_state.is_select:
        return
    if execute_state.execution_options.get(SOFT_DELETE_INCLUDE_INACTIVE_OPTION, False):
        return
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            SoftDeleteMixin,
            lambda cls: cls.activo.is_(True) if hasattr(cls, "activo") else true(),
            include_aliases=True,
        )
    )


def get_session() -> Generator[Session, None, None]:
    """Dependencia FastAPI: generador con yield (no contextmanager)."""
    with Session(engine) as session:
        yield session


__all__ = ["get_settings", "engine", "get_session", "SQLModel", "attach_engine_observability"]
