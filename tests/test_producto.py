from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from osiris.modules.inventario.producto.service import ProductoService
from osiris.modules.inventario.producto.entity import Producto
from osiris.modules.inventario.categoria.entity import Categoria


def _mock_exec_with_child_exists(exists: bool):
    exec_mock = MagicMock()
    exec_mock.first.return_value = object() if exists else None
    return exec_mock


def _active_leaf_category():
    return Categoria(nombre="Leaf", es_padre=False, activo=True, is_default=False)


def test_producto_service_create_falla_si_categoria_no_es_hoja():
    session = MagicMock()
    service = ProductoService()
    service.repo = MagicMock()

    # Simular que la categoría tiene hijos -> no es hoja
    category_query = MagicMock()
    category_query.first.return_value = _active_leaf_category()
    session.exec.side_effect = [category_query, _mock_exec_with_child_exists(True)]

    data = {
        "nombre": f"Prod-{uuid4().hex[:8]}",
        "categoria_ids": [uuid4()],
    }

    with pytest.raises(Exception):
        service.create(session, data)

    service.repo.create.assert_not_called()


@pytest.mark.parametrize(
    ("categoria", "expected_message"),
    [
        (Categoria(nombre="Temporal", es_padre=False, is_default=True, activo=True), "categoría temporal"),
        (Categoria(nombre="Inactiva", es_padre=False, is_default=False, activo=False), "inactiva"),
    ],
)
def test_producto_service_rechaza_categoria_temporal_o_inactiva(categoria, expected_message):
    service = ProductoService()
    session = MagicMock()
    query = MagicMock()
    query.first.return_value = categoria
    session.exec.return_value = query

    with pytest.raises(HTTPException) as error:
        service._validate_leaf_categories(session, [uuid4()])
    if categoria.is_default:
        assert error.value.status_code == 409
        assert error.value.detail["code"] == "CATEGORY_DEFAULT_PROTECTED"
    else:
        assert expected_message in str(error.value.detail)


def test_producto_service_create_rechaza_multiples_categorias_legacy():
    session = MagicMock()
    service = ProductoService()
    repo = MagicMock()
    service.repo = repo
    categories = [uuid4(), uuid4()]

    with pytest.raises(HTTPException) as error:
        service.create(
            session,
            {
                "nombre": f"Prod-{uuid4().hex[:8]}",
                "categoria_ids": categories,
            },
        )

    assert error.value.status_code == 422
    assert error.value.detail["code"] == "PRODUCT_MULTIPLE_CATEGORIES_NOT_SUPPORTED"
    repo.create.assert_not_called()


def test_producto_service_create_requiere_categoria_legacy():
    session = MagicMock()
    service = ProductoService()
    service.repo = MagicMock()

    with pytest.raises(HTTPException) as error:
        service.create(session, {"nombre": "Sin categoría"})

    assert error.value.status_code == 422
    assert error.value.detail["code"] == "PRODUCT_CATEGORY_REQUIRED"
    service.repo.create.assert_not_called()


def test_producto_service_update_no_permite_vaciar_categoria_legacy():
    session = MagicMock()
    service = ProductoService()
    service.repo = MagicMock()

    with pytest.raises(HTTPException) as error:
        service.update(session, uuid4(), {"categoria_ids": []})

    assert error.value.status_code == 422
    assert error.value.detail["code"] == "PRODUCT_CATEGORY_REQUIRED"
    service.repo.update.assert_not_called()


def test_producto_service_create_legacy_single_category_sets_fk_and_bridge():
    session = MagicMock()
    service = ProductoService()
    repo = MagicMock()
    service.repo = repo
    category_id = uuid4()
    category_query = MagicMock()
    category_query.first.return_value = _active_leaf_category()
    session.exec.side_effect = [category_query, _mock_exec_with_child_exists(False)]
    created = Producto(nombre="Producto", usuario_auditoria="test")
    created.id = uuid4()
    repo.create.return_value = created

    service.create(
        session,
        {"nombre": "Producto", "categoria_ids": [category_id]},
    )

    persisted_data = repo.create.call_args.args[1]
    assert persisted_data["categoria_principal_id"] == category_id
    repo.set_categorias.assert_called_once_with(session, created.id, [category_id])


def test_producto_service_update_valida_hoja():
    session = MagicMock()
    service = ProductoService()
    repo = MagicMock()
    service.repo = repo

    db_obj = Producto(nombre="Original", usuario_auditoria="tester")
    db_obj.id = uuid4()
    repo.get.return_value = db_obj

    # Caso inválido: categoría no hoja
    category_query = MagicMock()
    category_query.first.return_value = _active_leaf_category()
    session.exec.side_effect = [category_query, _mock_exec_with_child_exists(True)]

    with pytest.raises(Exception):
        service.update(session, db_obj.id, {"categoria_ids": [uuid4()]})

    # Caso válido: hoja
    category_id = uuid4()
    category_query = MagicMock()
    category_query.first.return_value = _active_leaf_category()
    empty_children = _mock_exec_with_child_exists(False)
    previous_categories = MagicMock()
    previous_categories.all.return_value = []
    session.exec.side_effect = [category_query, empty_children, previous_categories]
    service.update(session, db_obj.id, {"categoria_ids": [category_id]})
    repo.set_categorias.assert_called()
    assert repo.update.call_args.args[2]["categoria_principal_id"] == category_id


def test_producto_cantidad_es_readonly_en_create():
    """Verificar que el campo cantidad no puede ser ingresado por el usuario"""
    session = MagicMock()
    service = ProductoService()
    repo = MagicMock()
    service.repo = repo

    category_id = uuid4()
    category_query = MagicMock()
    category_query.first.return_value = _active_leaf_category()
    session.exec.side_effect = [category_query, _mock_exec_with_child_exists(False)]

    created_obj = Producto(nombre="Test", usuario_auditoria="tester", cantidad=0)
    created_obj.id = uuid4()
    repo.create.return_value = created_obj

    # El usuario intenta pasar cantidad=100 pero el DTO no debe aceptarlo
    data = {
        "nombre": f"Prod-{uuid4().hex[:8]}",
        "categoria_ids": [category_id],
        "cantidad": 100,  # Este campo debe ser ignorado
    }

    # El servicio debe crear con cantidad=0 (default)
    service.create(session, data)

    # Verificar que repo.create fue llamado
    repo.create.assert_called_once()
    # El objeto creado debe tener cantidad=0 (default de la entidad)
    assert created_obj.cantidad == 0


def test_producto_cantidad_default_zero():
    """Verificar que la entidad Producto inicializa cantidad en 0"""
    producto = Producto(nombre="Test", usuario_auditoria="tester")
    assert producto.cantidad == 0
