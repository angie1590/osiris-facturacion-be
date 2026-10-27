from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa
from sqlmodel import Session

from osiris.core.catalog_lock import (
    CATALOG_MUTATION_LOCK_KEY,
    acquire_catalog_mutation_lock,
)


def test_lock_requires_outer_transaction_and_never_commits_or_flushes():
    session = MagicMock(spec=Session)
    session.in_transaction.return_value = True
    session.get_bind.return_value.dialect.name = "postgresql"
    session.connection.return_value.get_execution_options.return_value = {}

    acquire_catalog_mutation_lock(session)

    statement, params = session.connection.return_value.execute.call_args.args
    assert str(statement) == "SELECT pg_advisory_xact_lock(:catalog_lock_key)"
    assert params == {"catalog_lock_key": CATALOG_MUTATION_LOCK_KEY}
    session.commit.assert_not_called()
    session.rollback.assert_not_called()
    session.flush.assert_not_called()
    session.no_autoflush.__enter__.assert_called_once()


def test_lock_without_transaction_fails_before_database_access():
    session = MagicMock(spec=Session)
    session.in_transaction.return_value = False
    with pytest.raises(RuntimeError, match="transaccion exterior"):
        acquire_catalog_mutation_lock(session)
    session.connection.assert_not_called()


def test_sqlite_does_not_pretend_to_support_catalog_lock():
    engine = sa.create_engine("sqlite://")
    try:
        with Session(engine) as session, session.begin():
            with pytest.raises(RuntimeError, match="PostgreSQL"):
                acquire_catalog_mutation_lock(session)
    finally:
        engine.dispose()


def test_autocommit_connection_is_not_accepted():
    session = MagicMock(spec=Session)
    session.in_transaction.return_value = True
    session.get_bind.return_value.dialect.name = "postgresql"
    session.connection.return_value.get_execution_options.return_value = {"isolation_level": "AUTOCOMMIT"}
    with pytest.raises(RuntimeError, match="AUTOCOMMIT"):
        acquire_catalog_mutation_lock(session)
    session.connection.return_value.execute.assert_not_called()


@pytest.fixture
def catalog_postgresql_engine():
    value = os.getenv("CATALOG_TEST_DATABASE_URL")
    if not value:
        pytest.skip("Requiere CATALOG_TEST_DATABASE_URL autorizado; estas pruebas solo usan SELECT y advisory locks.")
    url = sa.engine.make_url(value)
    if url.get_backend_name() != "postgresql":
        pytest.fail("CATALOG_TEST_DATABASE_URL debe apuntar a PostgreSQL.")
    engine = sa.create_engine(url.set(drivername="postgresql+psycopg"), connect_args={"options": "-c statement_timeout=5000 -c lock_timeout=3000"})
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.mark.parametrize("finish", ["commit", "rollback"])
def test_postgresql_lock_serializes_sessions_and_releases_on_transaction_end(catalog_postgresql_engine, finish):
    with Session(catalog_postgresql_engine) as first, Session(catalog_postgresql_engine) as second:
        first.begin()
        second.begin()
        acquire_catalog_mutation_lock(first)
        acquired = second.execute(
            sa.text("SELECT pg_try_advisory_xact_lock(:key)"),
            {"key": CATALOG_MUTATION_LOCK_KEY},
        ).scalar_one()
        assert acquired is False
        if finish == "commit":
            first.commit()
        else:
            first.rollback()
        acquired_after = second.execute(
            sa.text("SELECT pg_try_advisory_xact_lock(:key)"),
            {"key": CATALOG_MUTATION_LOCK_KEY},
        ).scalar_one()
        assert acquired_after is True
        acquire_catalog_mutation_lock(second)
        second.rollback()


def test_postgresql_engine_autocommit_is_rejected_even_without_execution_option(catalog_postgresql_engine):
    engine = sa.create_engine(catalog_postgresql_engine.url, isolation_level="AUTOCOMMIT")
    try:
        with Session(engine) as session, session.begin():
            assert "isolation_level" not in session.connection().get_execution_options()
            with pytest.raises(RuntimeError, match="AUTOCOMMIT"):
                acquire_catalog_mutation_lock(session)
    finally:
        engine.dispose()