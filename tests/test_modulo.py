"""
Tests unitarios para el módulo Modulo
"""
from unittest.mock import MagicMock

from osiris.modules.common.modulo.service import ModuloService


def test_modulo_validate_create():
    """Test validación de creación de módulo."""
    service = ModuloService()
    session = MagicMock()

    data = {
        "codigo": "TEST_MOD",
        "nombre": "Módulo de Prueba",
        "orden": 10,
        "usuario_auditoria": "test_user"
    }

    # validate_create no debe lanzar excepción
    service.validate_create(data, session)


def test_modulo_validate_update():
    """Test validación de actualización de módulo."""
    service = ModuloService()
    session = MagicMock()

    data = {
        "nombre": "Nombre Actualizado",
        "orden": 20,
        "usuario_auditoria": "test_user"
    }

    # validate_update no debe lanzar excepción
    service.validate_update(data, session)


def test_modulo_service_hereda_base_service():
    """Test que ModuloService hereda correctamente de BaseService."""
    service = ModuloService()

    # Verificar que tiene los métodos heredados
    assert hasattr(service, 'create')
    assert hasattr(service, 'get')
    assert hasattr(service, 'list_paginated')
    assert hasattr(service, 'update')
    assert hasattr(service, 'delete')
