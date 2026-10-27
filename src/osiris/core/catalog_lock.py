from __future__ import annotations

import sqlalchemy as sa
from sqlmodel import Session


CATALOG_MUTATION_LOCK_KEY = int.from_bytes(b"OSIRISC1", byteorder="big", signed=True)


def acquire_catalog_mutation_lock(session: Session) -> None:
    if not session.in_transaction():
        raise RuntimeError("El lock de catalogo requiere una transaccion exterior activa.")
    if session.get_bind().dialect.name != "postgresql":
        raise RuntimeError("El lock transaccional de catalogo requiere PostgreSQL.")
    with session.no_autoflush:
        connection = session.connection()
        if connection.get_execution_options().get("isolation_level") == "AUTOCOMMIT":
            raise RuntimeError("El lock de catalogo no permite conexiones AUTOCOMMIT.")
        if getattr(connection.connection.dbapi_connection, "autocommit", False) is True:
            raise RuntimeError("El lock de catalogo no permite conexiones AUTOCOMMIT.")
        connection.execute(
            sa.text("SELECT pg_advisory_xact_lock(:catalog_lock_key)"),
            {"catalog_lock_key": CATALOG_MUTATION_LOCK_KEY},
        )