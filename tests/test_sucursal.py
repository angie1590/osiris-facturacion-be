# tests/unit/test_sucursal_unit.py
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from osiris.core.db import get_session
from osiris.main import app
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.sucursal.models import SucursalCreate, SucursalUpdate
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.common.sucursal.service import SucursalService
from osiris.modules.common.sucursal.repository import SucursalRepository
from osiris.modules.sri.tipo_contribuyente.entity import TipoContribuyente


# =======================
# DTOs: validaciones
# =======================

def test_sucursal_create_ok():
    dto = SucursalCreate(
        codigo="001",
        nombre="Sucursal Centro",
        direccion="Av. Principal 123",
        telefono="022345678",
        empresa_id=uuid4(),
        usuario_auditoria="tester",
    )
    assert dto.codigo == "001"
    assert dto.nombre.startswith("Sucursal")
    assert dto.telefono == "022345678"


def test_sucursal_create_codigo_invalido_falla():
    with pytest.raises(ValidationError):
        SucursalCreate(
            codigo="1",  # debe ser 3 chars
            nombre="Suc",
            direccion="Dir",
            empresa_id=uuid4(),
            usuario_auditoria="tester",
        )


def test_sucursal_update_parcial_ok():
    dto = SucursalUpdate(
        nombre="Nuevo Nombre",
        telefono="0987654321",
    )
    assert dto.nombre == "Nuevo Nombre"
    assert dto.telefono == "0987654321"


# =======================
# Service: create valida FK empresa
# =======================

def test_sucursal_service_create_empresa_not_found_404():
    session = MagicMock()
    session.exec.return_value.first.return_value = None  # Empresa no existe

    svc = SucursalService()

    payload = {
        "codigo": "001",
        "nombre": "Sucursal X",
        "direccion": "Dir",
        "empresa_id": uuid4(),
    }

    with pytest.raises(HTTPException) as exc:
        svc.create(session, payload)

    assert exc.value.status_code == 404
    assert "Empresa" in exc.value.detail


def test_sucursal_service_create_ok_commit_y_refresh():
    session = MagicMock()
    session.exec.return_value.first.return_value = object()  # Empresa existe

    svc = SucursalService()

    payload = {
        "codigo": "001",
        "nombre": "Sucursal X",
        "direccion": "Dir",
        "usuario_auditoria": "tester",
        "empresa_id": uuid4(),
    }

    out = svc.create(session, payload)
    assert out.codigo == "001"
    session.add.assert_called_once()
    session.commit.assert_called_once()
    session.refresh.assert_called_once()


def test_sucursal_service_create_duplica_codigo_devuelve_400():
    session = MagicMock()
    session.exec.return_value.first.return_value = object()  # Empresa existe
    session.commit.side_effect = IntegrityError(
        statement="INSERT INTO tbl_sucursal ...",
        params={},
        orig=Exception("duplicate key value violates unique constraint uq_sucursal_empresa_codigo"),
    )
    svc = SucursalService()

    payload = {
        "codigo": "002",
        "nombre": "Sucursal Sur",
        "direccion": "Dir",
        "usuario_auditoria": "tester",
        "empresa_id": uuid4(),
    }

    with pytest.raises(HTTPException) as exc:
        svc.create(session, payload)

    assert exc.value.status_code == 400
    assert exc.value.detail == "La empresa ya posee una sucursal con ese código"
    session.rollback.assert_called_once()


# =======================
# Service: list_by_empresa (paginado)
# =======================

def test_sucursal_service_list_by_empresa_retorna_items_y_meta():
    session = MagicMock()
    svc = SucursalService()
    svc.repo = MagicMock()
    svc.repo.list.return_value = (["s1", "s2"], 5)

    items, meta = svc.list_by_empresa(
        session,
        empresa_id=uuid4(),
        limit=2,
        offset=0,
        only_active=True,
    )

    assert items == ["s1", "s2"]
    assert meta.total == 5
    assert meta.limit == 2
    assert meta.offset == 0
    assert meta.has_more is True  # 5 > 2


# =======================
# Repository: delete lógico
# =======================

def test_sucursal_repository_delete_logico():
    session = MagicMock()
    repo = SucursalRepository()

    obj = Sucursal(
        codigo="013",
        nombre="Suc",
        direccion="Dir",
        empresa_id=uuid4(),
        usuario_auditoria="tester",
        activo=True,
    )
    ok = repo.delete(session, obj)
    assert ok is True
    assert obj.activo is False
    session.add.assert_called_once_with(obj)
    session.flush.assert_called_once()
    session.commit.assert_not_called()
    # opcional: garantizar que no refrescamos
    session.refresh.assert_not_called()


def _engine_sqlite():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_sucursal_codigo_unico_por_empresa():
    engine = _engine_sqlite()
    Sucursal.__table__.create(bind=engine)
    empresa_id = uuid4()

    with Session(engine) as session:
        session.add(
            Sucursal(
                codigo="002",
                nombre="Sucursal Norte",
                direccion="Quito",
                es_matriz=False,
                empresa_id=empresa_id,
            )
        )
        session.commit()

        session.add(
            Sucursal(
                codigo="002",
                nombre="Sucursal Duplicada",
                direccion="Quito",
                es_matriz=False,
                empresa_id=empresa_id,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_sucursal_matriz_solo_puede_ser_001():
    engine = _engine_sqlite()
    Sucursal.__table__.create(bind=engine)

    with Session(engine) as session:
        session.add(
            Sucursal(
                codigo="002",
                nombre="Sucursal Incorrecta",
                direccion="Guayaquil",
                es_matriz=True,
                empresa_id=uuid4(),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


@pytest.fixture
def sucursal_api_client():
    engine = _engine_sqlite()
    SQLModel.metadata.create_all(
        engine,
        tables=[
            TipoContribuyente.__table__,
            Empresa.__table__,
            Sucursal.__table__,
        ],
    )

    with Session(engine) as session:
        session.add(TipoContribuyente(codigo="01", nombre="Sociedad", activo=True))
        session.flush()

        empresa = Empresa(
            razon_social="Empresa Sucursal API",
            nombre_comercial="Empresa Sucursal API",
            ruc="1790012345001",
            direccion_matriz="Av. Matriz 100",
            telefono="022000000",
            obligado_contabilidad=False,
            tipo_contribuyente_id="01",
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(empresa)
        session.commit()
        session.refresh(empresa)
        empresa_id = empresa.id

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            yield client, empresa_id
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_sucursal_api_create_con_lat_long_ok(sucursal_api_client):
    client, empresa_id = sucursal_api_client
    payload = {
        "codigo": "001",
        "nombre": "Sucursal Matriz",
        "direccion": "Quito",
        "telefono": "022345678",
        "latitud": "-0.229850",
        "longitud": "-78.524948",
        "es_matriz": True,
        "empresa_id": str(empresa_id),
        "usuario_auditoria": "tester",
    }

    response = client.post("/api/v1/sucursales", json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert Decimal(str(body["latitud"])) == Decimal("-0.229850")
    assert Decimal(str(body["longitud"])) == Decimal("-78.524948")


def test_sucursal_api_update_con_lat_long_ok(sucursal_api_client):
    client, empresa_id = sucursal_api_client
    create_response = client.post(
        "/api/v1/sucursales",
        json={
            "codigo": "001",
            "nombre": "Sucursal Matriz",
            "direccion": "Quito",
            "es_matriz": True,
            "empresa_id": str(empresa_id),
            "usuario_auditoria": "tester",
        },
    )
    assert create_response.status_code == 201, create_response.text
    sucursal_id = create_response.json()["id"]

    update_response = client.put(
        f"/api/v1/sucursales/{sucursal_id}",
        json={
            "latitud": "-1.250000",
            "longitud": "-79.900000",
            "usuario_auditoria": "tester",
        },
    )
    assert update_response.status_code == 200, update_response.text
    body = update_response.json()
    assert Decimal(str(body["latitud"])) == Decimal("-1.250000")
    assert Decimal(str(body["longitud"])) == Decimal("-79.900000")


def test_sucursal_api_get_incluye_lat_long(sucursal_api_client):
    client, empresa_id = sucursal_api_client
    create_response = client.post(
        "/api/v1/sucursales",
        json={
            "codigo": "001",
            "nombre": "Sucursal Matriz",
            "direccion": "Quito",
            "latitud": "-2.100000",
            "longitud": "-80.700000",
            "es_matriz": True,
            "empresa_id": str(empresa_id),
            "usuario_auditoria": "tester",
        },
    )
    assert create_response.status_code == 201, create_response.text
    sucursal_id = create_response.json()["id"]

    get_response = client.get(f"/api/v1/sucursales/{sucursal_id}")
    assert get_response.status_code == 200, get_response.text
    body = get_response.json()
    assert "latitud" in body
    assert "longitud" in body
    assert Decimal(str(body["latitud"])) == Decimal("-2.100000")
    assert Decimal(str(body["longitud"])) == Decimal("-80.700000")


def test_sucursal_api_latitud_fuera_de_rango_devuelve_400(sucursal_api_client):
    client, empresa_id = sucursal_api_client
    response = client.post(
        "/api/v1/sucursales",
        json={
            "codigo": "001",
            "nombre": "Sucursal Matriz",
            "direccion": "Quito",
            "latitud": "91",
            "es_matriz": True,
            "empresa_id": str(empresa_id),
            "usuario_auditoria": "tester",
        },
    )
    assert response.status_code == 400, response.text
    assert "latitud" in response.json()["detail"].lower()


def test_sucursal_api_longitud_fuera_de_rango_devuelve_400(sucursal_api_client):
    client, empresa_id = sucursal_api_client
    response = client.post(
        "/api/v1/sucursales",
        json={
            "codigo": "001",
            "nombre": "Sucursal Matriz",
            "direccion": "Quito",
            "longitud": "181",
            "es_matriz": True,
            "empresa_id": str(empresa_id),
            "usuario_auditoria": "tester",
        },
    )
    assert response.status_code == 400, response.text
    assert "longitud" in response.json()["detail"].lower()
