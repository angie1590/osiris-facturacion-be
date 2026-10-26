"""
Tests unitarios para el módulo Modulo
"""

from unittest.mock import MagicMock
from uuid import UUID, uuid4

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from osiris.modules.common.modulo.service import ModuloService
from osiris.core.db import get_session
from osiris.domain.router import register_crud_routes


def test_modulo_validate_create():
    """Test validación de creación de módulo."""
    service = ModuloService()
    session = MagicMock()

    data = {
        "codigo": "TEST_MOD",
        "nombre": "Módulo de Prueba",
        "orden": 10,
        "usuario_auditoria": "test_user",
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
        "usuario_auditoria": "test_user",
    }

    # validate_update no debe lanzar excepción
    service.validate_update(data, session)


def test_modulo_service_hereda_base_service():
    """Test que ModuloService hereda correctamente de BaseService."""
    service = ModuloService()

    # Verificar que tiene los métodos heredados
    assert hasattr(service, "create")
    assert hasattr(service, "get")
    assert hasattr(service, "list_paginated")
    assert hasattr(service, "update")
    assert hasattr(service, "delete")


def test_dynamic_crud_preserves_concrete_payload_schema_and_request_validation():
    class CreateRecord(BaseModel):
        nombre: str

    class UpdateRecord(BaseModel):
        nombre: str | None = None

    class ReadRecord(CreateRecord):
        id: UUID

    service = MagicMock()
    service.create.return_value = {"id": str(uuid4()), "nombre": "Registro"}
    router = APIRouter()
    register_crud_routes(
        router=router,
        prefix="records",
        tags=["Records"],
        model_read=ReadRecord,
        model_create=CreateRecord,
        model_update=UpdateRecord,
        service=service,
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_session] = lambda: MagicMock()
    schema = app.openapi()
    assert schema["paths"]["/records"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/CreateRecord")
    assert schema["paths"]["/records/{item_id}"]["put"]["requestBody"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/UpdateRecord")
    with TestClient(app) as client:
        assert client.post("/records", json={"nombre": "Registro"}).status_code == 201
        assert client.post("/records", json={}).status_code == 422
    service.create.assert_called_once()
    assert service.create.call_args.args[1] == {"nombre": "Registro"}
