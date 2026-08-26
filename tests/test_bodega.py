"""
Tests unitarios para Bodega
"""
from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from osiris.modules.inventario.bodega.service import BodegaService
from osiris.modules.inventario.bodega.entity import Bodega
from osiris.modules.inventario.bodega.models import (
    BodegaCreate,
    BodegaUpdate,
)


def test_bodega_service_create_ok():
    """Verificar que create instancia y persiste la bodega"""
    session = MagicMock()
    service = BodegaService()

    empresa_id = uuid4()
    sucursal_id = uuid4()

    dto = BodegaCreate(
        codigo_bodega="BOD001",
        nombre_bodega="Bodega Principal",
        descripcion="Bodega principal de la empresa",
        empresa_id=empresa_id,
        sucursal_id=sucursal_id,
    )

    created_entity = Bodega(
        codigo_bodega="BOD001",
        nombre_bodega="Bodega Principal",
        descripcion="Bodega principal de la empresa",
        empresa_id=empresa_id,
        sucursal_id=sucursal_id,
        usuario_auditoria="api",
        activo=True,
    )
    created_entity.id = uuid4()

    def mock_refresh(entity):
        entity.id = created_entity.id

    session.refresh.side_effect = mock_refresh

    service.create(session, dto, usuario_auditoria="test_user")

    session.add.assert_called_once()
    session.commit.assert_called_once()
    session.refresh.assert_called_once()


def test_bodega_service_create_sin_sucursal():
    """Verificar que create funciona sin sucursal (bodega de matriz)"""
    session = MagicMock()
    service = BodegaService()

    empresa_id = uuid4()

    dto = BodegaCreate(
        codigo_bodega="BOD002",
        nombre_bodega="Bodega Matriz",
        descripcion=None,
        empresa_id=empresa_id,
        sucursal_id=None,
    )

    created_entity = Bodega(
        codigo_bodega="BOD002",
        nombre_bodega="Bodega Matriz",
        descripcion=None,
        empresa_id=empresa_id,
        sucursal_id=None,
        usuario_auditoria="api",
        activo=True,
    )
    created_entity.id = uuid4()

    def mock_refresh(entity):
        entity.id = created_entity.id

    session.refresh.side_effect = mock_refresh

    service.create(session, dto, usuario_auditoria="test_user")

    session.add.assert_called_once()
    session.commit.assert_called_once()
    session.refresh.assert_called_once()


def test_bodega_service_update_ok():
    """Verificar que update modifica campos permitidos"""
    session = MagicMock()
    service = BodegaService()

    entity_id = uuid4()
    empresa_id = uuid4()
    existing = Bodega(
        codigo_bodega="BOD001",
        nombre_bodega="Bodega Original",
        descripcion="Descripción original",
        empresa_id=empresa_id,
        sucursal_id=None,
        usuario_auditoria="original",
        activo=True,
    )
    existing.id = entity_id

    session.get.return_value = existing

    dto = BodegaUpdate(
        codigo_bodega="BOD001-UPD",
        nombre_bodega="Bodega Actualizada",
        descripcion="Nueva descripción",
    )

    result = service.update(session, entity_id, dto, usuario_auditoria="test_user")

    assert result is not None
    assert result.codigo_bodega == "BOD001-UPD"
    assert result.nombre_bodega == "Bodega Actualizada"
    assert result.descripcion == "Nueva descripción"
    session.add.assert_called_once()
    session.commit.assert_called_once()
    session.refresh.assert_called_once()


def test_bodega_service_update_not_found():
    """Verificar que update retorna None si no existe la entidad"""
    session = MagicMock()
    service = BodegaService()

    entity_id = uuid4()
    session.get.return_value = None

    dto = BodegaUpdate(nombre_bodega="No existe")

    result = service.update(session, entity_id, dto, usuario_auditoria="test_user")

    assert result is None
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_bodega_service_delete_soft_ok():
    """Verificar que delete marca activo=False"""
    session = MagicMock()
    service = BodegaService()

    entity_id = uuid4()
    empresa_id = uuid4()
    existing = Bodega(
        codigo_bodega="BOD001",
        nombre_bodega="Bodega a eliminar",
        descripcion=None,
        empresa_id=empresa_id,
        sucursal_id=None,
        usuario_auditoria="original",
        activo=True,
    )
    existing.id = entity_id

    session.get.return_value = existing

    # Query 1: productos asignados -> None
    # Query 2: saldo stock -> 0
    first_result = MagicMock()
    first_result.first.return_value = None
    second_result = MagicMock()
    second_result.one.return_value = 0
    session.exec.side_effect = [first_result, second_result]

    result = service.delete(session, entity_id, usuario_auditoria="test_user")

    assert result is True
    assert existing.activo is False
    assert existing.usuario_auditoria == "test_user"
    session.add.assert_called_once()
    session.commit.assert_called_once()


def test_bodega_service_delete_not_found():
    """Verificar que delete retorna False si no existe la entidad"""
    session = MagicMock()
    service = BodegaService()

    entity_id = uuid4()
    session.get.return_value = None

    result = service.delete(session, entity_id, usuario_auditoria="test_user")

    assert result is False
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_bodega_service_delete_con_productos_asignados_falla():
    session = MagicMock()
    service = BodegaService()

    entity_id = uuid4()
    existing = Bodega(
        codigo_bodega="BOD001",
        nombre_bodega="Bodega ocupada",
        descripcion=None,
        empresa_id=uuid4(),
        sucursal_id=None,
        usuario_auditoria="original",
        activo=True,
    )
    existing.id = entity_id
    session.get.return_value = existing

    first_result = MagicMock()
    first_result.first.return_value = uuid4()
    session.exec.return_value = first_result

    with pytest.raises(HTTPException) as exc:
        service.delete(session, entity_id, usuario_auditoria="test_user")

    assert exc.value.status_code == 400
    assert "tiene productos asignados" in exc.value.detail.lower()


def test_bodega_service_get_ok():
    """Verificar que get retorna la entidad si existe"""
    session = MagicMock()
    service = BodegaService()

    entity_id = uuid4()
    empresa_id = uuid4()
    existing = Bodega(
        codigo_bodega="BOD001",
        nombre_bodega="Bodega Test",
        descripcion=None,
        empresa_id=empresa_id,
        sucursal_id=None,
        usuario_auditoria="test",
        activo=True,
    )
    existing.id = entity_id

    session.get.return_value = existing

    result = service.get(session, entity_id)

    assert result is not None
    assert result.id == entity_id
    assert result.codigo_bodega == "BOD001"


def test_bodega_service_list_paginated():
    """Verificar que list_paginated retorna lista de entidades activas"""
    session = MagicMock()
    service = BodegaService()

    # Mock exec para simular query result
    mock_result = [
        Bodega(
            codigo_bodega="BOD001",
            nombre_bodega="Bodega 1",
            descripcion=None,
            empresa_id=uuid4(),
            sucursal_id=None,
            usuario_auditoria="test",
            activo=True,
        ),
        Bodega(
            codigo_bodega="BOD002",
            nombre_bodega="Bodega 2",
            descripcion=None,
            empresa_id=uuid4(),
            sucursal_id=None,
            usuario_auditoria="test",
            activo=True,
        ),
    ]

    session.exec.return_value = mock_result

    result = service.list_paginated(session, skip=0, limit=50)

    assert len(result) == 2
    session.exec.assert_called_once()
