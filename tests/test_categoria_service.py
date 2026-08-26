import uuid
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from sqlmodel import Session

from osiris.modules.inventario.categoria.service import CategoriaService  # noqa: E402


def make_db_obj(id_: uuid.UUID, parent_id=None):
    # Use a simple plain object to avoid importing SQLModel declarative classes
    return SimpleNamespace(id=id_, nombre="x", es_padre=False, parent_id=parent_id)


def test_validate_create_calls_fk_check_when_parent_id_present():
    service = CategoriaService()
    session = Mock(spec=Session)

    data = {"nombre": "X", "es_padre": False, "parent_id": str(uuid.uuid4())}

    # Patch the fk check
    service._check_fk_active_and_exists = Mock()

    # Should not raise
    service.validate_create(data, session)

    service._check_fk_active_and_exists.assert_called_once_with(session, data)


def test_update_self_reference_raises():
    service = CategoriaService()
    session = Mock(spec=Session)

    item_id = uuid.uuid4()
    db_obj = make_db_obj(item_id)

    service.repo = Mock()
    service.repo.get.return_value = db_obj

    # Use UUID type to ensure equality check in service catches self-reference
    data = {"parent_id": item_id}

    with pytest.raises(HTTPException) as exc:
        service.update(session, item_id, data)

    assert "parent_id no puede referenciar" in str(exc.value.detail)


def test_update_detects_cycle_and_raises():
    service = CategoriaService()
    session = Mock(spec=Session)

    item_id = uuid.uuid4()
    other_id = uuid.uuid4()
    db_obj = make_db_obj(item_id, parent_id=None)

    service.repo = Mock()
    service.repo.get.return_value = db_obj

    # Patch detect cycle to True
    service._detect_cycle = Mock(return_value=True)

    data = {"parent_id": str(other_id)}

    with pytest.raises(HTTPException) as exc:
        service.update(session, item_id, data)

    service._detect_cycle.assert_called_once()
    assert "ciclo" in str(exc.value.detail)


def test_update_calls_repo_update_on_success():
    service = CategoriaService()
    session = Mock(spec=Session)

    item_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    db_obj = make_db_obj(item_id, parent_id=None)

    service.repo = Mock()
    service.repo.get.return_value = db_obj

    # Ensure detect_cycle is False
    service._detect_cycle = Mock(return_value=False)
    service._check_fk_active_and_exists = Mock()

    expected = {"id": str(item_id), "nombre": "updated"}
    service.repo.update.return_value = expected

    data = {"parent_id": str(parent_id), "nombre": "updated"}

    res = service.update(session, item_id, data)

    service._check_fk_active_and_exists.assert_called_once()
    service.repo.update.assert_called_once()
    assert res == expected
