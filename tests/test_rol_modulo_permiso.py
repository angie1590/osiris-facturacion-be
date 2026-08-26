"""
Tests unitarios para el módulo RolModuloPermiso
"""
from unittest.mock import MagicMock

from osiris.modules.common.rol_modulo_permiso.service import RolModuloPermisoService


def test_permiso_validate_create():
    """Test validación de creación de permiso."""
    service = RolModuloPermisoService()
    session = MagicMock()

    data = {
        "rol_id": "uuid-rol",
        "modulo_id": "uuid-modulo",
        "puede_leer": True,
        "puede_crear": False,
        "usuario_auditoria": "test_user"
    }

    # validate_create no debe lanzar excepción
    service.validate_create(data, session)


def test_permiso_validate_update():
    """Test validación de actualización de permiso."""
    service = RolModuloPermisoService()
    session = MagicMock()

    data = {
        "puede_leer": True,
        "puede_crear": True,
        "puede_actualizar": True,
        "usuario_auditoria": "test_user"
    }

    # validate_update no debe lanzar excepción
    service.validate_update(data, session)


def test_permiso_service_hereda_base_service():
    """Test que RolModuloPermisoService hereda correctamente de BaseService."""
    service = RolModuloPermisoService()

    # Verificar que tiene los métodos heredados
    assert hasattr(service, 'create')
    assert hasattr(service, 'get')
    assert hasattr(service, 'list_paginated')
    assert hasattr(service, 'update')
    assert hasattr(service, 'delete')
    # Métodos específicos
    assert hasattr(service, 'obtener_permisos_por_rol')
    assert hasattr(service, 'obtener_menu_por_rol')
