from __future__ import annotations

from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException

from osiris.modules.inventario.categoria.service import CategoriaService
from osiris.modules.inventario.categoria.repository import CategoriaRepository
from osiris.modules.inventario.categoria.entity import Categoria


def test_categoria_validate_create_parent_rules():
    service = CategoriaService()
    session = MagicMock()
    # Ahora parent_id es opcional: si viene, se valida la FK; si no viene, no falla
    data = {"nombre": "Padre", "es_padre": True, "parent_id": "some-uuid"}
    service._check_fk_active_and_exists = MagicMock()
    # No debe lanzar; debe delegar la validación del FK
    service.validate_create(data, session)
    service._check_fk_active_and_exists.assert_called_once_with(session, data)

    # Caso: es_padre False y sin parent_id -> no debe fallar ahora
    data = {"nombre": "Hijo", "es_padre": False}
    service.validate_create(data, session)


def test_categoria_create_checks_fk_exists():
    service = CategoriaService()
    # Simular que session.exec(...).first() devuelve None (no existe parent)
    session = MagicMock()
    mock_exec = MagicMock()
    mock_exec.first.return_value = None
    session.exec.return_value = mock_exec

    # es_padre False y parent_id dado -> validate_create pasa, pero _check_fk... falla con 404
    data = {"nombre": "Hijo", "es_padre": False, "parent_id": "00000000-0000-0000-0000-000000000001"}
    with pytest.raises(HTTPException) as exc:
        service.create(session, data)
    assert exc.value.status_code == 404


def test_categoria_update_cleans_parent_and_prevents_self_ref():
    service = CategoriaService()
    service.repo = MagicMock(spec=CategoriaRepository)
    session = MagicMock()

    # objeto existente con parent_id diferente
    existing = Categoria(nombre="Old", es_padre=False, parent_id=None)
    item_id = "11111111-1111-1111-1111-111111111111"
    service.repo.get.return_value = existing

    # Caso: actualizar a es_padre True -> parent_id se mantiene si se proporciona
    service.repo.update.return_value = existing
    data = {"es_padre": True, "parent_id": "22222222-2222-2222-2222-222222222222"}
    service.update(session, item_id, data)
    # repo.update fue llamado y parent_id se conserva (argumento en posición 2)
    called_data = service.repo.update.call_args[0][2]
    assert called_data.get("parent_id") == "22222222-2222-2222-2222-222222222222"

    # Caso: evitar self-reference
    data = {"es_padre": False, "parent_id": item_id}
    with pytest.raises(HTTPException) as exc2:
        service.update(session, item_id, data)
    assert exc2.value.status_code == 400


def test_categoria_repository_delete_logico():
    repo = CategoriaRepository()
    session = MagicMock()
    obj = Categoria(nombre="Temp", es_padre=True, usuario_auditoria="tester", activo=True)
    ok = repo.delete(session, obj)
    assert ok is True
    assert obj.activo is False
    session.add.assert_called_once_with(obj)
    session.flush.assert_called_once()
    session.commit.assert_not_called()
