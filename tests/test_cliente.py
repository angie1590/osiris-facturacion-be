# tests/test_repository_integrity.py
from __future__ import annotations

from uuid import uuid4
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from osiris.modules.common.cliente.service import ClienteService
from osiris.modules.common.cliente.repository import ClienteRepository
from osiris.modules.common.cliente.models import ClienteCreate
from osiris.modules.common.cliente.entity import Cliente


# -----------------------
# Helpers para IntegrityError de PG
# -----------------------

class _Diag:
    def __init__(self, constraint_name=None, column_name=None, table_name=None):
        self.constraint_name = constraint_name
        self.column_name = column_name
        self.table_name = table_name

class _PGOrig:
    """Simula error PostgreSQL con pgcode y diag.*"""
    def __init__(self, pgcode, constraint=None, column=None, table=None, text=""):
        self.pgcode = pgcode
        self.diag = _Diag(constraint, column, table)
        self._text = text

    def __str__(self):
        return self._text or f"PG error {self.pgcode}"


def _mk_integrity_error(pgcode, *, constraint=None, column=None, table=None, text=""):
    return IntegrityError("stmt", {}, _PGOrig(pgcode, constraint, column, table, text))


# -----------------------
# Test: CREATE (unique -> 409)
# -----------------------

def test_cliente_create_unique_persona_mapea_a_409_con_mensaje_claro():
    """
    Simula un duplicado de persona_id:
    - commit() lanza IntegrityError 23505 con constraint 'ix_tbl_cliente_persona_id'
    - Debe traducirse a HTTP 409 con mensaje específico (según BaseRepository._raise_integrity)
    """
    session = MagicMock()
    session.add = MagicMock()
    # Fuerza IntegrityError de UNIQUE
    session.commit.side_effect = _mk_integrity_error(
        "23505", constraint="ix_tbl_cliente_persona_id"
    )
    session.refresh = MagicMock()

    service = ClienteService()
    service.repo = ClienteRepository()  # usa BaseRepository con el handler genérico

    dto = ClienteCreate(
        persona_id=uuid4(),
        tipo_cliente_id=uuid4(),
        usuario_auditoria="admin",
    )

    with pytest.raises(HTTPException) as exc:
        service.create(session, dto)

    assert exc.value.status_code == 409
    # Mensaje mapeado por constraint conocida
    assert "ya está registrada como cliente" in exc.value.detail


# -----------------------
# Test: UPDATE (FK -> 409)
# -----------------------

def test_repository_update_fk_violation_mapea_a_409():
    """
    Simula violación de FK (23503) al hacer update; el repo debe traducir a 409 con detalle útil.
    """
    session = MagicMock()
    session.add = MagicMock()
    session.flush.side_effect = _mk_integrity_error(
        "23503", constraint="fk_tbl_cliente_tipo_cliente_id", table="tbl_cliente"
    )

    repo = ClienteRepository()
    db_obj = Cliente(persona_id=uuid4(), tipo_cliente_id=uuid4(), usuario_auditoria="x")  # instancia válida

    with pytest.raises(HTTPException) as exc:
        repo.update(session, db_obj, {"tipo_cliente_id": uuid4()})

    assert exc.value.status_code == 409
    assert "llave foránea" in exc.value.detail.lower()
    assert "tbl_cliente" in exc.value.detail


# -----------------------
# Test: DELETE (FK -> 409) en hard delete
# -----------------------

def test_repository_delete_fk_violation_mapea_a_409_en_hard_delete():
    """
    Si el modelo NO tiene 'activo', BaseRepository.delete hace hard delete.
    Simulamos FK violation 23503 en commit -> 409.
    """
    # Modelo simple sin 'activo' para forzar hard delete
    class SinActivo:
        __tablename__ = "tbl_otro"
        id = uuid4()

    class FakeRepo(ClienteRepository):
        model = SinActivo  # no se usa en delete, pero mantenemos estructura

    session = MagicMock()
    session.delete = MagicMock()
    session.flush.side_effect = _mk_integrity_error(
        "23503", constraint="fk_tbl_otro_algo", table="tbl_otro"
    )

    repo = FakeRepo()
    db_obj = SinActivo()

    with pytest.raises(HTTPException) as exc:
        repo.delete(session, db_obj)

    assert exc.value.status_code == 409
    assert "llave foránea" in exc.value.detail.lower()
    assert "tbl_otro" in exc.value.detail


# -----------------------
# Test: DELETE (soft delete) NO debe lanzar si no hay error
# -----------------------

def test_repository_delete_soft_ok():
    """
    Si el modelo tiene 'activo', delete es lógico y commit no lanza -> True
    """
    class ConActivo:
        __tablename__ = "tbl_soft"
        def __init__(self):
            self.activo = True

    class FakeRepo(ClienteRepository):
        model = ConActivo

    session = MagicMock()
    session.flush = MagicMock()

    repo = FakeRepo()
    obj = ConActivo()
    ok = repo.delete(session, obj)

    assert ok is True
    assert obj.activo is False
    session.flush.assert_called_once()
    session.commit.assert_not_called()
