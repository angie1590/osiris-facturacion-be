"""
Tests unitarios para ProductoImpuesto (repository, service, asignación)
"""
import pytest
from datetime import date, timedelta
from uuid import uuid4
from unittest.mock import MagicMock
from fastapi import HTTPException

from osiris.modules.inventario.producto.entity import Producto, TipoProducto
from osiris.modules.sri.impuesto_catalogo.entity import (
    ImpuestoCatalogo,
    TipoImpuesto,
    AplicaA
)
from osiris.modules.inventario.producto.entity import ProductoImpuesto
from osiris.modules.inventario.producto_impuesto.repository import ProductoImpuestoRepository
from osiris.modules.inventario.producto_impuesto.service import ProductoImpuestoService


# ==================== REPOSITORY TESTS ====================

def test_repo_validar_maximo_por_tipo_cuando_ya_existe():
    """Debe lanzar HTTPException cuando ya existe 1 impuesto del mismo tipo"""
    repo = ProductoImpuestoRepository()
    session = MagicMock()

    producto_id = uuid4()

    # Mock count_by_tipo_impuesto para que devuelva 1
    repo.count_by_tipo_impuesto = MagicMock(return_value=1)

    with pytest.raises(HTTPException) as exc_info:
        repo.validar_maximo_por_tipo(session, producto_id, TipoImpuesto.IVA)
    assert exc_info.value.status_code == 400
    assert "máximo" in exc_info.value.detail.lower()


def test_repo_validar_maximo_por_tipo_cuando_no_existe():
    """No debe lanzar excepción cuando no hay impuestos del tipo"""
    repo = ProductoImpuestoRepository()
    session = MagicMock()

    producto_id = uuid4()

    # Mock count_by_tipo_impuesto para que devuelva 0
    repo.count_by_tipo_impuesto = MagicMock(return_value=0)

    # No debe lanzar excepción
    repo.validar_maximo_por_tipo(session, producto_id, TipoImpuesto.IVA)


def test_repo_validar_duplicado_cuando_existe():
    """Debe lanzar HTTPException cuando ya existe la combinación producto-impuesto"""
    repo = ProductoImpuestoRepository()
    session = MagicMock()

    producto_id = uuid4()
    impuesto_id = uuid4()

    # Mock get_by_producto_impuesto para que devuelva un registro
    repo.get_by_producto_impuesto = MagicMock(return_value=ProductoImpuesto(
        id=uuid4(),
        producto_id=producto_id,
        impuesto_catalogo_id=impuesto_id,
        activo=True,
        usuario_auditoria="test_user"
    ))

    with pytest.raises(HTTPException) as exc_info:
        repo.validar_duplicado(session, producto_id, impuesto_id)
    assert exc_info.value.status_code == 409


# ==================== SERVICE TESTS ====================

def test_service_asignar_impuesto_producto_no_existe():
    """No se puede asignar impuesto a producto inexistente"""
    service = ProductoImpuestoService()
    session = MagicMock()

    producto_id = uuid4()
    impuesto_id = uuid4()

    # Mock session.get para que devuelva None (producto no existe)
    session.get.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        service.asignar_impuesto(session, producto_id, impuesto_id, "test_user")
    assert exc_info.value.status_code == 404


def test_service_asignar_impuesto_producto_inactivo_falla():
    """No se puede asignar impuesto a producto inactivo"""
    service = ProductoImpuestoService()
    session = MagicMock()

    producto_id = uuid4()
    impuesto_id = uuid4()

    producto_inactivo = Producto(
        id=producto_id,
        nombre="Producto Test",
        tipo=TipoProducto.BIEN,
        pvp=100.0,
        activo=False,  # INACTIVO
        usuario_auditoria="test_user"
    )

    # Mock session.get para devolver producto inactivo
    session.get.return_value = producto_inactivo

    with pytest.raises(HTTPException) as exc_info:
        service.asignar_impuesto(session, producto_id, impuesto_id, "test_user")
    assert exc_info.value.status_code == 404
    assert "inactivo" in exc_info.value.detail.lower()


def test_service_validar_compatibilidad_tipo_bien_con_impuesto_solo_servicio():
    """Producto BIEN no puede tener impuesto solo para SERVICIO"""
    service = ProductoImpuestoService()

    with pytest.raises(HTTPException) as exc_info:
        service._validar_compatibilidad_tipo(TipoProducto.BIEN, AplicaA.SERVICIO)
    assert exc_info.value.status_code == 400
    assert "no aplica" in exc_info.value.detail.lower()


def test_service_validar_compatibilidad_tipo_bien_con_impuesto_ambos():
    """Producto BIEN puede tener impuesto para AMBOS"""
    service = ProductoImpuestoService()

    # No debe lanzar excepción
    service._validar_compatibilidad_tipo(TipoProducto.BIEN, AplicaA.AMBOS)


def test_service_validar_compatibilidad_tipo_servicio_con_impuesto_solo_bien():
    """Producto SERVICIO no puede tener impuesto solo para BIEN"""
    service = ProductoImpuestoService()

    with pytest.raises(HTTPException) as exc_info:
        service._validar_compatibilidad_tipo(TipoProducto.SERVICIO, AplicaA.BIEN)
    assert exc_info.value.status_code == 400
    assert "no aplica" in exc_info.value.detail.lower()


def test_service_eliminar_iva_siempre_rechazado():
    """No se puede eliminar IVA - es obligatorio (requerimiento SRI)"""
    service = ProductoImpuestoService()
    session = MagicMock()

    producto_id = uuid4()
    impuesto_id = uuid4()
    producto_impuesto_id = uuid4()

    # Mock: ProductoImpuesto existe y es IVA
    producto_impuesto = ProductoImpuesto(
        id=producto_impuesto_id,
        producto_id=producto_id,
        impuesto_catalogo_id=impuesto_id,
        activo=True,
        usuario_auditoria="test"
    )

    impuesto_iva = ImpuestoCatalogo(
        id=impuesto_id,
        tipo_impuesto=TipoImpuesto.IVA,
        codigo_tipo_impuesto="2",
        codigo_sri="2",
        descripcion="IVA 0%",
        vigente_desde=date.today(),
        aplica_a=AplicaA.AMBOS,
        activo=True,
        usuario_auditoria="test"
    )

    # Mock session.get para devolver producto_impuesto e impuesto
    def mock_get(model, id):
        if id == producto_impuesto_id:
            return producto_impuesto
        if id == impuesto_id:
            return impuesto_iva
        return None

    session.get = mock_get

    # Intentar eliminar IVA debe fallar siempre
    with pytest.raises(HTTPException) as exc_info:
        service.eliminar_impuesto(session, producto_impuesto_id)

    assert exc_info.value.status_code == 400
    assert "obligatorio" in exc_info.value.detail.lower()
    assert "iva" in exc_info.value.detail.lower()


def test_service_eliminar_ice_ok():
    """Se puede eliminar ICE u otros impuestos que no sean IVA"""
    service = ProductoImpuestoService()
    session = MagicMock()

    producto_id = uuid4()
    impuesto_id = uuid4()
    producto_impuesto_id = uuid4()

    # Mock: ProductoImpuesto con ICE
    producto_impuesto = ProductoImpuesto(
        id=producto_impuesto_id,
        producto_id=producto_id,
        impuesto_catalogo_id=impuesto_id,
        activo=True,
        usuario_auditoria="test"
    )

    impuesto_ice = ImpuestoCatalogo(
        id=impuesto_id,
        tipo_impuesto=TipoImpuesto.ICE,
        codigo_tipo_impuesto="3",
        codigo_sri="3",
        descripcion="ICE 10%",
        vigente_desde=date.today(),
        aplica_a=AplicaA.BIEN,
        activo=True,
        usuario_auditoria="test"
    )

    # Mock session.get
    def mock_get(model, id):
        if id == producto_impuesto_id:
            return producto_impuesto
        if id == impuesto_id:
            return impuesto_ice
        return None

    session.get = mock_get

    # Mock delete_by_id
    service.repo.delete_by_id = MagicMock(return_value=True)

    # Eliminar ICE debe ser exitoso
    result = service.eliminar_impuesto(session, producto_impuesto_id)
    assert result is True
    service.repo.delete_by_id.assert_called_once_with(session, producto_impuesto_id)


def test_service_asignar_impuesto_guarda_codigos_sri_y_tarifa_snapshot():
    service = ProductoImpuestoService()
    session = MagicMock()

    producto_id = uuid4()
    impuesto_id = uuid4()
    producto = Producto(
        id=producto_id,
        nombre="Producto Test",
        tipo=TipoProducto.BIEN,
        pvp=100.0,
        activo=True,
        usuario_auditoria="test_user",
    )
    impuesto = ImpuestoCatalogo(
        id=impuesto_id,
        tipo_impuesto=TipoImpuesto.IVA,
        codigo_tipo_impuesto="2",
        codigo_sri="4",
        descripcion="IVA 15%",
        vigente_desde=date.today() - timedelta(days=10),
        aplica_a=AplicaA.AMBOS,
        porcentaje_iva=15,
        activo=True,
        usuario_auditoria="test",
    )

    def mock_get(model, obj_id):
        if model is Producto and obj_id == producto_id:
            return producto
        if model is ImpuestoCatalogo and obj_id == impuesto_id:
            return impuesto
        return None

    session.get = mock_get
    service.repo.validar_duplicado = MagicMock()
    service.list_by_producto = MagicMock(return_value=[])
    service.impuesto_repo.es_vigente = MagicMock(return_value=True)
    service.repo.create = MagicMock(side_effect=lambda _session, obj: obj)

    result = service.asignar_impuesto(session, producto_id, impuesto_id, "tester")
    assert result.codigo_impuesto_sri == "2"
    assert result.codigo_porcentaje_sri == "4"
    assert str(result.tarifa) == "15"
