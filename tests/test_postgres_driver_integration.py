import sys
from pathlib import Path

from osiris.core.db import engine, get_engine


def test_postgres_driver_is_psycopg_v3_only() -> None:
    assert engine.url.drivername == "postgresql+psycopg"
    assert get_engine().url.drivername == "postgresql+psycopg"

    # En contexto de ejecucion de la app no deben cargarse drivers redundantes.
    assert "psycopg2" not in sys.modules
    assert "asyncpg" not in sys.modules


def test_pyproject_declares_single_postgres_driver() -> None:
    pyproject_text = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "psycopg (>=3" in pyproject_text
    assert "psycopg2-binary" not in pyproject_text
    assert "asyncpg (" not in pyproject_text


def test_engine_uses_pre_ping_for_stable_connections() -> None:
    assert getattr(engine.pool, "_pre_ping", False) is True
