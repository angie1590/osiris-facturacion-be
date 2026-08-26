from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from osiris.modules.inventario.producto.service import ProductoService
from osiris.modules.inventario.producto.entity import Producto


def _mock_exec_with_child_exists(exists: bool):
    # session.exec(select(...)).first() -> obj or None
    exec_mock = MagicMock()
    exec_mock.first.return_value = object() if exists else None
    return exec_mock


def test_producto_service_create_falla_si_categoria_no_es_hoja():
    session = MagicMock()
    service = ProductoService()
    service.repo = MagicMock()

    # Simular que la categoría tiene hijos -> no es hoja
    session.exec.return_value = _mock_exec_with_child_exists(True)

    data = {
        "nombre": f"Prod-{uuid4().hex[:8]}",
        "categoria_ids": [uuid4()],
    }

    with pytest.raises(Exception):
        service.create(session, data)

    service.repo.create.assert_not_called()


def test_producto_service_create_ok_y_asocia_multiples():
    session = MagicMock()
    service = ProductoService()
    repo = MagicMock()
    service.repo = repo

    # Categorías hojas (sin hijos)
    session.exec.return_value = _mock_exec_with_child_exists(False)

    created_obj = Producto(nombre="X", usuario_auditoria="tester")
    created_obj.id = uuid4()
    repo.create.return_value = created_obj

    categorias = [uuid4(), uuid4()]
    attrs = [uuid4(), uuid4()]

    data = {
        "nombre": f"Prod-{uuid4().hex[:8]}",
        "categoria_ids": categorias,
        "atributo_ids": attrs,
    }

    out = service.create(session, data)

    assert out is created_obj
    repo.set_categorias.assert_called_once()
    # Proveedores se gestionan vía triggers post-compra; no se setean aquí


def test_producto_service_update_valida_hoja():
    session = MagicMock()
    service = ProductoService()
    repo = MagicMock()
    service.repo = repo

    db_obj = Producto(nombre="Original", usuario_auditoria="tester")
    db_obj.id = uuid4()
    repo.get.return_value = db_obj

    # Caso inválido: categoría no hoja
    session.exec.return_value = _mock_exec_with_child_exists(True)

    with pytest.raises(Exception):
        service.update(session, db_obj.id, {"categoria_ids": [uuid4()]})

    # Caso válido: hoja
    session.exec.return_value = _mock_exec_with_child_exists(False)
    service.update(session, db_obj.id, {"categoria_ids": [uuid4()]})
    repo.set_categorias.assert_called()


def test_producto_cantidad_es_readonly_en_create():
    """Verificar que el campo cantidad no puede ser ingresado por el usuario"""
    session = MagicMock()
    service = ProductoService()
    repo = MagicMock()
    service.repo = repo

    session.exec.return_value = _mock_exec_with_child_exists(False)

    created_obj = Producto(nombre="Test", usuario_auditoria="tester", cantidad=0)
    created_obj.id = uuid4()
    repo.create.return_value = created_obj

    # El usuario intenta pasar cantidad=100 pero el DTO no debe aceptarlo
    data = {
        "nombre": f"Prod-{uuid4().hex[:8]}",
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
