from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from osiris.core.directory_permissions import directory_permission
from osiris.core.audit_context import set_current_user_id, reset_current_user_id
from osiris.modules.common.persona.composition import resolve_persona
from osiris.modules.common.usuario.entity import Usuario
from osiris.modules.common.rol.entity import Rol
from osiris.modules.common.modulo.entity import Modulo
from osiris.modules.common.rol_modulo_permiso.entity import RolModuloPermiso


def test_directory_guard_checks_effective_permission_not_role_name():
    session = MagicMock()
    session.info = {}
    session.get.return_value = MagicMock(activo=True)
    user = Usuario(persona_id=uuid4(), rol_id=uuid4(), username="administrator", password_hash="not-exposed")
    with patch("osiris.core.directory_permissions.requiere_permiso", side_effect=HTTPException(status_code=403, detail="Sin permiso")) as check:
        with pytest.raises(HTTPException) as exc:
            directory_permission("EMPLEADOS", "crear")(request=Request({"type": "http", "method": "POST", "path": "/api/v1/empleados", "headers": []}), usuario=user, session=session)
        assert exc.value.status_code == 403
        check.assert_called_once_with(session, user.id, "EMPLEADOS", "crear")
        event = session.add.call_args.args[0]
        assert event.accion == "UNAUTHORIZED_ACCESS"
        assert event.estado_nuevo["payload_intentado"] is None
        assert event.estado_nuevo["modulo"] == "EMPLEADOS"


def test_directory_guard_rejects_inactive_role():
    session = MagicMock()
    session.info = {}
    session.get.return_value = MagicMock(activo=False)
    user = Usuario(persona_id=uuid4(), rol_id=uuid4(), username="test", password_hash="not-exposed")
    with pytest.raises(HTTPException) as exc:
        directory_permission("USUARIOS", "actualizar")(request=Request({"type": "http", "method": "PUT", "path": "/api/v1/usuarios", "headers": []}), usuario=user, session=session)
    assert exc.value.status_code == 403


def test_embedded_person_permission_denial_rolls_back_and_audits_without_payload():
    session = MagicMock()
    session.info = {"directory_permission_request": Request({
        "type": "http", "method": "POST", "path": "/api/v1/clientes", "headers": [],
    })}
    actor = str(uuid4())
    token = set_current_user_id(actor)
    try:
        with patch("osiris.core.directory_permissions.requiere_permiso", side_effect=HTTPException(status_code=403, detail="Sin permiso Persona")):
            with pytest.raises(HTTPException) as error:
                resolve_persona(session, {"persona_id": uuid4()})
        assert error.value.status_code == 403
        session.exec.assert_not_called()
        session.rollback.assert_called_once()
        event = session.add.call_args.args[0]
        assert event.usuario_id == actor
        assert event.estado_nuevo["modulo"] == "PERSONAS"
        assert event.estado_nuevo["payload_intentado"] is None
    finally:
        reset_current_user_id(token)


def test_security_configuration_cannot_bypass_directory_guards_anonymously():
    from osiris.modules.common.rol.router import router as roles
    from osiris.modules.common.modulo.router import router as modules
    from osiris.modules.common.rol_modulo_permiso.router import router as permissions
    from osiris.core.db import get_session

    app = FastAPI()
    session = MagicMock()
    app.dependency_overrides[get_session] = lambda: session
    for router in (roles, modules, permissions):
        app.include_router(router)
    with TestClient(app) as client:
        for router in (roles, modules, permissions):
            for route in router.routes:
                for method in route.methods:
                    path = route.path.replace("{item_id}", str(uuid4()))
                    response = client.request(method, path, json={})
                    assert response.status_code == 401
    session.add.assert_not_called()
    session.commit.assert_not_called()


def _bootstrap_migration():
    path = Path(__file__).parents[1] / "src/osiris/db/alembic/versions/a9c3d6e41f82_directory_rbac_bootstrap.py"
    spec = importlib.util.spec_from_file_location("directory_rbac_bootstrap", path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_rbac_bootstrap_grants_only_admin_is_idempotent_and_preserves_admin_changes():
    engine = sa.create_engine("sqlite://")
    for model in (Rol, Modulo, RolModuloPermiso):
        model.__table__.create(engine)
    migration = _bootstrap_migration()
    administrator = Rol(nombre="Administrador", usuario_auditoria="test")
    operator = Rol(nombre="Vendedor", usuario_auditoria="test")
    try:
        with engine.begin() as connection:
            connection.execute(Rol.__table__.insert(), [administrator.model_dump(), operator.model_dump()])
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.upgrade()
                migration.upgrade()
            assert connection.scalar(sa.select(sa.func.count()).select_from(Modulo.__table__)) == 7
            grants = connection.execute(sa.select(RolModuloPermiso.__table__)).mappings().all()
            assert len(grants) == 7
            assert {grant["rol_id"] for grant in grants} == {administrator.id}
            assert all(grant["puede_crear"] and grant["puede_eliminar"] for grant in grants)
            grant_id = grants[0]["id"]
            connection.execute(RolModuloPermiso.__table__.update().where(RolModuloPermiso.id == grant_id).values(
                puede_eliminar=False, updated_by="real-admin",
            ))
            with Operations.context(context):
                migration.upgrade()
            assert connection.scalar(sa.select(RolModuloPermiso.puede_eliminar).where(RolModuloPermiso.id == grant_id)) is False
            with Operations.context(context), pytest.raises(RuntimeError, match="permisos administrados"):
                migration.downgrade()
            connection.execute(RolModuloPermiso.__table__.update().where(RolModuloPermiso.id == grant_id).values(updated_by=migration.ACTOR))
            with Operations.context(context):
                migration.downgrade()
            assert connection.scalar(sa.select(sa.func.count()).select_from(Modulo.__table__)) == 0
            assert connection.scalar(sa.select(sa.func.count()).select_from(Rol.__table__)) == 2
    finally:
        engine.dispose()