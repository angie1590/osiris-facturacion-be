from __future__ import annotations

import base64
import json
import time
from uuid import UUID
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION, get_session
from osiris.main import app
from osiris.modules.common.rol.entity import Rol
from osiris.modules.common.rol.repository import RolRepository


def _build_fake_jwt(sub: str) -> str:
    header = {"alg": "none", "typ": "JWT"}
    payload = {"sub": sub}
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{header_b64}.{payload_b64}."


def _build_test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine, tables=[Rol.__table__])
    return engine


def test_audit_mixin_auto_dates():
    engine = _build_test_engine()
    repo = RolRepository()

    with Session(engine) as session:
        rol = repo.create(
            session,
            {"nombre": f"ROL-{uuid4().hex[:8]}", "descripcion": "Inicial"},
        )
        assert rol.created_at is not None
        assert rol.updated_at is not None
        created_at = rol.created_at
        old_updated = rol.updated_at

        time.sleep(0.01)
        rol = repo.update(session, rol, {"descripcion": "Actualizado"})
        assert rol.created_at == created_at
        assert rol.updated_at > old_updated


def test_contextvar_user_injection():
    engine = _build_test_engine()

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        user_id = str(uuid4())
        token = _build_fake_jwt(user_id)
        payload = {"nombre": f"ROL-{uuid4().hex[:8]}", "descripcion": "Con contexto"}

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/roles",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 201

        with Session(engine) as session:
            rol = session.exec(select(Rol).where(Rol.nombre == payload["nombre"])).first()
            assert rol is not None
            assert rol.created_by == user_id
            assert rol.updated_by == user_id
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_soft_delete_exclusion():
    engine = _build_test_engine()

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        role_name = f"ROL-{uuid4().hex[:8]}"
        with TestClient(app) as client:
            create_resp = client.post("/api/v1/roles", json={"nombre": role_name, "descripcion": "SoftDelete"})
            assert create_resp.status_code == 201
            role_id = create_resp.json()["id"]

            list_before = client.get("/api/v1/roles")
            assert list_before.status_code == 200
            ids_before = {item["id"] for item in list_before.json()["items"]}
            assert role_id in ids_before

            delete_resp = client.delete(f"/api/v1/roles/{role_id}")
            assert delete_resp.status_code == 204

            list_after = client.get("/api/v1/roles")
            assert list_after.status_code == 200
            ids_after = {item["id"] for item in list_after.json()["items"]}
            assert role_id not in ids_after

        with Session(engine) as session:
            stmt = (
                select(Rol)
                .where(Rol.id == UUID(role_id))
                .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
            )
            obj = session.exec(stmt).first()
            assert obj is not None
            assert obj.activo is False
    finally:
        app.dependency_overrides.pop(get_session, None)
