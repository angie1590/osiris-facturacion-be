# tests/test_producto_bodega.py
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from osiris.modules.inventario.producto_bodega.service import ProductoBodegaService
from osiris.modules.inventario.producto.entity import ProductoBodega, Producto, TipoProducto


def test_producto_bodega_service_create_ok():
    """Verifica que se puede crear una relación producto-bodega"""
    from osiris.modules.inventario.producto.entity import Producto
    from osiris.modules.inventario.bodega.entity import Bodega

    session = MagicMock()
    service = ProductoBodegaService()
    repo = MagicMock()
    service.repo = repo

    producto_id = uuid4()
    bodega_id = uuid4()

    # Mock para simular producto y bodega existentes (FK validation)
    producto = Producto(nombre="Producto Test")
    producto.id = producto_id
    producto.activo = True

    bodega = Bodega(codigo_bodega="BOD001", nombre_bodega="Bodega Test")
    bodega.id = bodega_id
    bodega.activo = True

    # Mock para el orden correcto: duplicate check primero, luego FK validations
    def exec_side_effect(stmt):
        mock_result = MagicMock()
        # Primera llamada: verificación duplicado (retorna None - no existe)
        # Segunda llamada: validación FK producto (retorna producto)
        # Tercera llamada: validación FK bodega (retorna bodega)
        if not hasattr(exec_side_effect, 'call_count'):
            exec_side_effect.call_count = 0

        exec_side_effect.call_count += 1

        if exec_side_effect.call_count == 1:  # Duplicate check
            mock_result.first.return_value = None
        elif exec_side_effect.call_count == 2:  # FK producto
            mock_result.first.return_value = producto
        else:  # FK bodega
            mock_result.first.return_value = bodega

        return mock_result

    session.exec.side_effect = exec_side_effect

    created_obj = ProductoBodega(
        producto_id=producto_id,
        bodega_id=bodega_id,
        cantidad=Decimal("10.0000")
    )
    created_obj.id = uuid4()
    repo.create.return_value = created_obj

    data = {
        "producto_id": producto_id,
        "bodega_id": bodega_id,
        "cantidad": 10,
    }

    result = service.create(session, data)
    assert result is created_obj
    repo.create.assert_called_once()


def test_producto_bodega_service_create_producto_invalido_falla():
    """Verifica que falla si el producto_id no existe"""
    session = MagicMock()
    service = ProductoBodegaService()

    # Mock para simular que el producto no existe
    exec_mock = MagicMock()
    exec_mock.first.return_value = None
    session.exec.return_value = exec_mock

    data = {
        "producto_id": uuid4(),
        "bodega_id": uuid4(),
        "cantidad": 10,
    }

    with pytest.raises(HTTPException) as exc_info:
        service.create(session, data)

    assert exc_info.value.status_code == 404
    assert "Producto no encontrado" in exc_info.value.detail


def test_producto_bodega_service_create_duplicado_falla():
    """Verifica que no se puede crear una relación duplicada"""
    from osiris.modules.inventario.producto.entity import Producto
    from osiris.modules.inventario.bodega.entity import Bodega

    session = MagicMock()
    service = ProductoBodegaService()

    producto_id = uuid4()
    bodega_id = uuid4()

    # Mock para validaciones FK
    producto = Producto(nombre="Producto Test")
    producto.id = producto_id
    producto.activo = True

    bodega = Bodega(codigo_bodega="BOD001", nombre_bodega="Bodega Test")
    bodega.id = bodega_id
    bodega.activo = True

    # Mock para simular que ya existe la relación
    existing_relation = ProductoBodega(
        producto_id=producto_id,
        bodega_id=bodega_id,
        cantidad=Decimal("5.0000")
    )

    # El duplicate check es lo primero que se ejecuta
    exec_mock = MagicMock()
    exec_mock.first.return_value = existing_relation  # Ya existe
    session.exec.return_value = exec_mock

    data = {
        "producto_id": producto_id,
        "bodega_id": bodega_id,
        "cantidad": 10,
    }

    with pytest.raises(HTTPException) as exc_info:
        service.create(session, data)

    assert exc_info.value.status_code == 409
    assert "ya está asignado" in exc_info.value.detail


def test_producto_bodega_update_cantidad_crea_si_no_existe():
    """Verifica que update_cantidad crea la relación si no existe"""
    session = MagicMock()
    service = ProductoBodegaService()

    # Mock para que no exista la relación
    exec_mock = MagicMock()
    exec_mock.first.return_value = None
    session.exec.return_value = exec_mock

    producto_id = uuid4()
    bodega_id = uuid4()
    cantidad = 15

    service.update_cantidad(session, producto_id, bodega_id, cantidad)

    session.add.assert_called()
    session.commit.assert_called_once()
    session.refresh.assert_called_once()


def test_producto_bodega_update_cantidad_actualiza_si_existe():
    """Verifica que update_cantidad actualiza la cantidad si existe"""
    session = MagicMock()
    service = ProductoBodegaService()

    # Mock para simular relación existente
    existing = ProductoBodega(
        producto_id=uuid4(),
        bodega_id=uuid4(),
        cantidad=5
    )
    existing.id = uuid4()

    exec_mock = MagicMock()
    exec_mock.first.return_value = existing
    session.exec.return_value = exec_mock

    nueva_cantidad = 20
    service.update_cantidad(session, existing.producto_id, existing.bodega_id, nueva_cantidad)

    assert existing.cantidad == nueva_cantidad
    session.add.assert_called()
    session.commit.assert_called_once()


def test_producto_servicio_no_puede_tener_stock_en_create():
    session = MagicMock()
    service = ProductoBodegaService()

    # No existe relación previa
    exec_mock = MagicMock()
    exec_mock.first.return_value = None
    session.exec.return_value = exec_mock

    # Producto tipo SERVICIO
    prod = Producto(nombre="Servicio X")
    prod.id = uuid4()
    prod.tipo = TipoProducto.SERVICIO
    session.get.return_value = prod

    data = {
        "producto_id": prod.id,
        "bodega_id": uuid4(),
        "cantidad": 5,
    }

    with pytest.raises(HTTPException) as exc:
        service.create(session, data)
    assert exc.value.status_code == 400
    assert "servicios no pueden tener stock" in exc.value.detail.lower()


def test_producto_servicio_no_puede_tener_stock_en_update():
    session = MagicMock()
    service = ProductoBodegaService()

    # Producto tipo SERVICIO
    prod = Producto(nombre="Servicio Y")
    prod.id = uuid4()
    prod.tipo = TipoProducto.SERVICIO
    session.get.return_value = prod

    with pytest.raises(HTTPException) as exc:
        service.update_cantidad(session, prod.id, uuid4(), 3)
    assert exc.value.status_code == 400
    assert "servicios no pueden tener stock" in exc.value.detail.lower()


def test_producto_bodega_get_bodegas_by_producto():
    """Verifica que se pueden obtener todas las bodegas de un producto"""
    session = MagicMock()
    service = ProductoBodegaService()

    producto_id = uuid4()

    # Mock de datos
    from osiris.modules.inventario.bodega.entity import Bodega

    bodega1 = Bodega(codigo_bodega="BOD001", nombre_bodega="Bodega Principal")
    bodega1.id = uuid4()

    bodega2 = Bodega(codigo_bodega="BOD002", nombre_bodega="Bodega Secundaria")
    bodega2.id = uuid4()

    rel1 = ProductoBodega(producto_id=producto_id, bodega_id=bodega1.id, cantidad=10)
    rel1.id = uuid4()

    rel2 = ProductoBodega(producto_id=producto_id, bodega_id=bodega2.id, cantidad=5)
    rel2.id = uuid4()

    exec_mock = MagicMock()
    exec_mock.all.return_value = [(rel1, bodega1), (rel2, bodega2)]
    session.exec.return_value = exec_mock

    result = service.get_bodegas_by_producto(session, producto_id)

    assert len(result) == 2
    assert result[0]["codigo_bodega"] == "BOD001"
    assert result[0]["cantidad"] == Decimal("10.0000")
    assert result[1]["codigo_bodega"] == "BOD002"
    assert result[1]["cantidad"] == Decimal("5.0000")


def test_producto_bodega_get_productos_by_bodega():
    """Verifica que se pueden obtener todos los productos de una bodega"""
    session = MagicMock()
    service = ProductoBodegaService()

    bodega_id = uuid4()

    # Mock de datos
    from osiris.modules.inventario.producto.entity import Producto

    prod1 = Producto(nombre="Producto A")
    prod1.id = uuid4()

    prod2 = Producto(nombre="Producto B")
    prod2.id = uuid4()

    rel1 = ProductoBodega(producto_id=prod1.id, bodega_id=bodega_id, cantidad=Decimal("50.0000"))
    rel1.id = uuid4()

    rel2 = ProductoBodega(producto_id=prod2.id, bodega_id=bodega_id, cantidad=Decimal("30.0000"))
    rel2.id = uuid4()

    exec_mock = MagicMock()
    exec_mock.all.return_value = [(rel1, prod1), (rel2, prod2)]
    session.exec.return_value = exec_mock

    result = service.get_productos_by_bodega(session, bodega_id)

    assert len(result) == 2
    assert result[0]["nombre"] == "Producto A"
    assert result[0]["cantidad"] == Decimal("50.0000")
    assert result[1]["nombre"] == "Producto B"
    assert result[1]["cantidad"] == Decimal("30.0000")


def test_producto_bodega_create_bodega_inactiva_falla():
    session = MagicMock()
    service = ProductoBodegaService()

    producto_id = uuid4()
    bodega_id = uuid4()
    prod = Producto(nombre="Prod", tipo=TipoProducto.BIEN)
    prod.id = producto_id
    prod.activo = True
    prod.permite_fracciones = True

    bod = MagicMock()
    bod.id = bodega_id
    bod.activo = False

    def get_side_effect(model, _id):
        if model is Producto:
            return prod
        return bod

    session.get.side_effect = get_side_effect
    exec_mock = MagicMock()
    exec_mock.first.return_value = None
    session.exec.return_value = exec_mock

    with pytest.raises(HTTPException) as exc:
        service.create(
            session,
            {"producto_id": producto_id, "bodega_id": bodega_id, "cantidad": Decimal("1.0000")},
        )

    assert exc.value.status_code == 409
    assert "bodega inactiva" in exc.value.detail.lower()
