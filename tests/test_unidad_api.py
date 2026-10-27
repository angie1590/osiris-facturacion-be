from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, select

from osiris.core.db import get_session
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.catalogo.entity import Catalogo
from osiris.modules.common.modulo.entity import Modulo
from osiris.modules.common.rol.entity import Rol
from osiris.modules.common.rol_modulo_permiso.entity import RolModuloPermiso
from osiris.modules.common.unidad.entity import Unidad
from osiris.modules.common.unidad.router import router
from osiris.modules.common.unidad.seeds import crear_unidades_sistema
from osiris.modules.common.usuario.entity import Usuario
from osiris.modules.inventario.atributo.entity import (
    Atributo,
    AtributoCambio,
    TipoDato,
)


@pytest.fixture
def api() -> Iterator[tuple[TestClient, Session, Usuario, UUID]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for model in (
        Rol,
        Usuario,
        Modulo,
        RolModuloPermiso,
        AuditLog,
        Catalogo,
        Unidad,
        Atributo,
        AtributoCambio,
    ):
        SQLModel.metadata.create_all(engine, tables=[model.__table__])
    session = Session(engine)
    role = Rol(nombre="Operador")
    user = Usuario(
        persona_id=uuid4(),
        rol_id=role.id,
        username="unit-test",
        password_hash="unused",
    )
    module = Modulo(codigo="UNIDADES", nombre="Unidades")
    grant = RolModuloPermiso(
        rol_id=role.id,
        modulo_id=module.id,
        puede_leer=True,
        puede_crear=True,
        puede_actualizar=True,
        puede_eliminar=True,
    )
    seed = crear_unidades_sistema()[0]
    session.add_all([role, user, module, grant, seed])
    session.commit()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_session] = lambda: session
    with patch(
        "osiris.core.auth.decode_token",
        return_value={"sub": str(user.id), "type": "access"},
    ):
        with TestClient(app) as client:
            yield client, session, user, seed.id
    session.close()
    engine.dispose()


def test_unit_crud_filters_audit_and_seed_protection(
    api: tuple[TestClient, Session, Usuario, UUID],
) -> None:
    client, session, user, seed_id = api
    headers = {"Authorization": "Bearer test-unit"}
    response = client.post(
        "/api/v1/unidades",
        headers=headers,
        json={
            "codigo": "MEGABIT",
            "nombre": "Megabit",
            "simbolo": "Mb",
            "magnitud_codigo": "DATA_STORAGE",
        },
    )
    assert response.status_code == 201
    unit_id = response.json()["id"]
    assert response.json()["created_by"] == str(user.id)

    duplicate_code = client.post(
        "/api/v1/unidades",
        headers=headers,
        json={
            "codigo": "megabit",
            "nombre": "Otro nombre",
            "simbolo": "mB2",
            "magnitud_codigo": "DATA_STORAGE",
        },
    )
    assert duplicate_code.status_code == 409
    assert duplicate_code.json()["detail"]["code"] == "UNIT_DUPLICATE_CODE"

    duplicate_symbol = client.post(
        "/api/v1/unidades",
        headers=headers,
        json={
            "codigo": "OTRA_UNIDAD",
            "nombre": "Otro nombre",
            "simbolo": "u",
            "magnitud_codigo": "COUNT",
        },
    )
    assert duplicate_symbol.status_code == 409
    assert duplicate_symbol.json()["detail"]["code"] == "UNIT_DUPLICATE_SYMBOL"

    protected_update = client.put(
        f"/api/v1/unidades/{seed_id}", headers=headers, json={"nombre": "Cambio"}
    )
    protected_delete = client.delete(f"/api/v1/unidades/{seed_id}", headers=headers)
    assert protected_update.status_code == protected_delete.status_code == 409
    assert protected_update.json()["detail"]["code"] == "UNIT_PROTECTED"
    assert protected_delete.json()["detail"]["code"] == "UNIT_PROTECTED"

    listing = client.get(
        "/api/v1/unidades",
        headers=headers,
        params={"q": "MB", "magnitud_codigo": "DATA_STORAGE", "only_active": False},
    )
    assert listing.status_code == 200
    assert listing.json()["meta"]["total"] == 1
    assert listing.json()["items"][0]["simbolo"] == "Mb"

    deleted = client.delete(f"/api/v1/unidades/{unit_id}", headers=headers)
    assert deleted.status_code == 200 and deleted.json()["activo"] is False
    reactivated = client.post(f"/api/v1/unidades/{unit_id}/reactivar", headers=headers)
    assert reactivated.status_code == 200 and reactivated.json()["activo"] is True
    audit = session.exec(
        select(AuditLog).where(AuditLog.entidad_id == UUID(unit_id))
    ).all()
    assert [event.accion for event in audit] == [
        "CREATE_UNIT",
        "DEACTIVATE_UNIT",
        "REACTIVATE_UNIT",
    ]
    assert all(event.usuario_id == str(user.id) for event in audit)


def test_unit_routes_require_effective_permissions(
    api: tuple[TestClient, Session, Usuario, UUID],
) -> None:
    client, session, _user, _seed_id = api
    grant = session.exec(select(RolModuloPermiso)).one()
    grant.puede_crear = False
    session.add(grant)
    session.commit()
    before = len(session.exec(select(Unidad)).all())
    response = client.post(
        "/api/v1/unidades",
        headers={"Authorization": "Bearer test-unit"},
        json={
            "codigo": "TEST_UNIT",
            "nombre": "Unidad prueba",
            "simbolo": "tu",
            "magnitud_codigo": "COUNT",
        },
    )
    assert response.status_code == 403
    assert len(session.exec(select(Unidad)).all()) == before
    assert session.exec(select(AuditLog)).all() == []


def test_unit_usage_includes_current_attributes_and_json_snapshots(
    api: tuple[TestClient, Session, Usuario, UUID],
) -> None:
    client, session, _user, _seed_id = api
    headers = {"Authorization": "Bearer test-unit"}
    created = client.post(
        "/api/v1/unidades",
        headers=headers,
        json={
            "codigo": "RAM_UNIT",
            "nombre": "Unidad RAM",
            "simbolo": "ru",
            "magnitud_codigo": "DATA_STORAGE",
        },
    )
    unit_id = UUID(created.json()["id"])
    current_attribute = Atributo(
        nombre="RAM actual",
        tipo_dato=TipoDato.INTEGER,
        unidad_id=unit_id,
    )
    historical_attribute = Atributo(
        nombre="RAM historica",
        tipo_dato=TipoDato.INTEGER,
        activo=False,
    )
    session.add_all([current_attribute, historical_attribute])
    session.flush()
    session.add(
        AtributoCambio(
            atributo_id=historical_attribute.id,
            operacion="update",
            definicion_anterior={
                "codigo": "ram_historica",
                "tipo_dato": "integer",
                "unidad_id": str(unit_id),
            },
            definicion_posterior={
                "codigo": "ram_historica",
                "tipo_dato": "integer",
                "unidad_id": None,
            },
            asignaciones_anteriores=[],
            asignaciones_posteriores=[],
            valores_anteriores=[],
            valores_posteriores=[],
            remapeos_anteriores=[],
            remapeos_posteriores=[],
        )
    )
    session.commit()

    detail = client.get(f"/api/v1/unidades/{unit_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["uso"] == {
        "atributos_activos": 1,
        "atributos_inactivos": 0,
        "snapshots_historicos": 1,
    }

    descriptive_update = client.put(
        f"/api/v1/unidades/{unit_id}",
        headers=headers,
        json={"nombre": "Unidad RAM revisada"},
    )
    assert descriptive_update.status_code == 200
    assert descriptive_update.json()["nombre"] == "Unidad RAM revisada"

    semantic_update = client.put(
        f"/api/v1/unidades/{unit_id}",
        headers=headers,
        json={"simbolo": "RAM"},
    )
    assert semantic_update.status_code == 409
    assert semantic_update.json()["detail"]["code"] == "UNIT_IN_USE"

    deactivation = client.delete(f"/api/v1/unidades/{unit_id}", headers=headers)
    assert deactivation.status_code == 409
    assert deactivation.json()["detail"]["code"] == "UNIT_IN_USE"