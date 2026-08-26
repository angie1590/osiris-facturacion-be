"""
Tests unitarios para utilidades de permisos
"""
from unittest.mock import MagicMock, Mock
import pytest
from fastapi import HTTPException

from osiris.core.permisos import verificar_permiso, requiere_permiso


def test_verificar_permiso_retorna_true_con_permiso():
    """Test verificar_permiso retorna True cuando el usuario tiene el permiso."""
    session = MagicMock()

    # Mock usuario activo con rol
    mock_usuario = Mock()
    mock_usuario.activo = True
    mock_usuario.rol_id = "rol-uuid"

    # Mock módulo encontrado
    mock_modulo = Mock()
    mock_modulo.id = "modulo-uuid"

    # Mock permiso encontrado con puede_leer=True
    mock_permiso = Mock()
    mock_permiso.puede_leer = True

    # Configurar session.exec para devolver mocks en secuencia
    session.get.return_value = mock_usuario
    def side_effect_select(*args, **kwargs):
        # primera llamada: módulo, segunda: permiso
        class R:
            def first(self_inner):
                return side_effect_select.values.pop(0)
        return R()
    side_effect_select.values = [mock_modulo, mock_permiso]
    session.exec.side_effect = side_effect_select

    resultado = verificar_permiso(session, "usuario-uuid", "MODULO", "leer")
    assert resultado is True


def test_verificar_permiso_retorna_false_sin_permiso():
    """Test verificar_permiso retorna False cuando el permiso está en False."""
    session = MagicMock()

    mock_usuario = Mock()
    mock_usuario.activo = True
    mock_usuario.rol_id = "rol-uuid"

    mock_modulo = Mock()
    mock_modulo.id = "modulo-uuid"

    mock_permiso = Mock()
    mock_permiso.puede_crear = False

    session.get.return_value = mock_usuario
    def side_effect_select(*args, **kwargs):
        class R:
            def first(self_inner):
                return side_effect_select.values.pop(0)
        return R()
    side_effect_select.values = [mock_modulo, mock_permiso]
    session.exec.side_effect = side_effect_select

    resultado = verificar_permiso(session, "usuario-uuid", "MODULO", "crear")
    assert resultado is False


def test_verificar_permiso_usuario_inactivo():
    """Test verificar_permiso retorna False si el usuario está inactivo."""
    session = MagicMock()

    mock_usuario = Mock()
    mock_usuario.activo = False

    session.get.return_value = mock_usuario

    resultado = verificar_permiso(session, "usuario-uuid", "MODULO", "leer")
    assert resultado is False


def test_verificar_permiso_modulo_inexistente():
    """Test verificar_permiso retorna False si el módulo no existe."""
    session = MagicMock()

    mock_usuario = Mock()
    mock_usuario.activo = True
    mock_usuario.rol_id = "rol-uuid"

    session.get.return_value = mock_usuario
    def side_effect_select(*args, **kwargs):
        class R:
            def first(self_inner):
                return None
        return R()
    session.exec.side_effect = side_effect_select

    resultado = verificar_permiso(session, "usuario-uuid", "INEXISTENTE", "leer")
    assert resultado is False


def test_verificar_permiso_sin_registro():
    """Test verificar_permiso retorna False si no hay registro de permiso."""
    session = MagicMock()

    mock_usuario = Mock()
    mock_usuario.activo = True
    mock_usuario.rol_id = "rol-uuid"

    mock_modulo = Mock()
    mock_modulo.id = "modulo-uuid"

    session.get.return_value = mock_usuario
    def side_effect_select(*args, **kwargs):
        class R:
            def first(self_inner):
                return side_effect_select.values.pop(0)
        return R()
    side_effect_select.values = [mock_modulo, None]
    session.exec.side_effect = side_effect_select

    resultado = verificar_permiso(session, "usuario-uuid", "MODULO", "leer")
    assert resultado is False


def test_requiere_permiso_no_lanza_excepcion_con_permiso():
    """Test requiere_permiso no lanza excepción si hay permiso."""
    session = MagicMock()

    mock_usuario = Mock()
    mock_usuario.activo = True
    mock_usuario.rol_id = "rol-uuid"

    mock_modulo = Mock()
    mock_modulo.id = "modulo-uuid"

    mock_permiso = Mock()
    mock_permiso.puede_leer = True

    session.get.return_value = mock_usuario
    def side_effect_select(*args, **kwargs):
        class R:
            def first(self_inner):
                return side_effect_select.values.pop(0)
        return R()
    side_effect_select.values = [mock_modulo, mock_permiso]
    session.exec.side_effect = side_effect_select

    # No debe lanzar excepción
    requiere_permiso(session, "usuario-uuid", "MODULO", "leer")


def test_requiere_permiso_lanza_403_sin_permiso():
    """Test requiere_permiso lanza HTTPException 403 si no hay permiso."""
    session = MagicMock()

    mock_usuario = Mock()
    mock_usuario.activo = True
    mock_usuario.rol_id = "rol-uuid"

    mock_modulo = Mock()
    mock_modulo.id = "modulo-uuid"

    mock_permiso = Mock()
    mock_permiso.puede_crear = False

    session.get.return_value = mock_usuario
    def side_effect_select(*args, **kwargs):
        class R:
            def first(self_inner):
                return side_effect_select.values.pop(0)
        return R()
    side_effect_select.values = [mock_modulo, mock_permiso]
    session.exec.side_effect = side_effect_select

    with pytest.raises(HTTPException) as exc_info:
        requiere_permiso(session, "usuario-uuid", "MODULO", "crear")

    assert exc_info.value.status_code == 403
