from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlmodel import Session, select

from osiris.core.audit_context import (
    extract_auth_context_from_request_headers,
    reset_current_company_id,
    reset_current_user_id,
    set_current_company_id,
    set_current_user_id,
)
from osiris.core.auth import create_token
from osiris.core.db import get_session
from osiris.core.security import hash_password, verify_password
from osiris.modules.common.auth_router import router as auth_router
from osiris.modules.common.empleado.entity import Empleado
from osiris.modules.common.empleado.models import EmpleadoCreate
from osiris.modules.common.empleado.repository import EmpleadoRepository
from osiris.modules.common.empleado.router import router as empleado_router
from osiris.modules.common.empleado.service import EmpleadoService
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.modulo.entity import Modulo
from osiris.modules.common.persona.entity import Persona
from osiris.modules.common.rol.entity import Rol
from osiris.modules.common.rol_modulo_permiso.entity import RolModuloPermiso
from osiris.modules.common.usuario.entity import Usuario
from osiris.modules.common.usuario.models import UsuarioCreate, UsuarioUpdate
from osiris.modules.common.usuario.repository import UsuarioRepository
from osiris.modules.common.usuario.router import router as usuario_router
from osiris.modules.common.usuario.service import UsuarioService
from osiris.modules.sri.tipo_contribuyente.entity import TipoContribuyente


@pytest.fixture
def directory_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'directory.db'}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def configure_connection(connection, _record):
        connection.isolation_level = None
        connection.execute("PRAGMA foreign_keys=ON")

    @event.listens_for(engine, "begin")
    def begin_transaction(connection):
        connection.exec_driver_sql("BEGIN")

    for model in (TipoContribuyente, Persona, Rol, Empresa, Usuario, Empleado, Modulo, RolModuloPermiso):
        model.__table__.create(engine)
    with Session(engine, expire_on_commit=False) as session:
        session.add(TipoContribuyente(codigo="01", nombre="Natural"))
        person = Persona(identificacion="ADMIN1", tipo_identificacion="PASAPORTE", nombre="Admin", apellido="Directorio")
        role = Rol(nombre="Administrador")
        session.add_all([person, role])
        session.flush()
        company = Empresa(razon_social="Empresa de prueba", ruc="1790012345001", direccion_matriz="Quito", tipo_contribuyente_id="01")
        session.add(company)
        actor = Usuario(persona_id=person.id, rol_id=role.id, username="admin", password_hash=hash_password("Admin12345"), requiere_cambio_password=False)
        session.add(actor)
        for code in ("PERSONAS", "USUARIOS", "EMPLEADOS"):
            module = Modulo(codigo=code, nombre=code)
            session.add(module)
            session.flush()
            session.add(RolModuloPermiso(rol_id=role.id, modulo_id=module.id, puede_leer=True, puede_crear=True, puede_actualizar=True, puede_eliminar=True))
        session.commit()
        database = SimpleNamespace(engine=engine, company_id=company.id, role_id=role.id, actor_id=actor.id, person_id=person.id)
    try:
        yield database
    finally:
        engine.dispose()


@pytest.fixture
def directory_client(directory_db):
    application = FastAPI()
    application.include_router(auth_router)
    application.include_router(usuario_router)
    application.include_router(empleado_router)

    def session_dependency():
        with Session(directory_db.engine) as session:
            yield session

    @application.middleware("http")
    async def audit_context(request, call_next):
        actor, company = extract_auth_context_from_request_headers(
            authorization=request.headers.get("authorization"), x_user_id=None,
            x_company_id=request.headers.get("x-company-id"),
        )
        actor_token = set_current_user_id(actor)
        company_token = set_current_company_id(company)
        try:
            return await call_next(request)
        finally:
            reset_current_user_id(actor_token)
            reset_current_company_id(company_token)

    application.dependency_overrides[get_session] = session_dependency
    with TestClient(application, raise_server_exceptions=False) as client:
        client.headers["Authorization"] = f"Bearer {create_token(directory_db.actor_id, 'access', timedelta(minutes=5))}"
        yield client


def user_payload(database, *, identity="NEW001", username="new-user"):
    return {
        "persona_nueva": {"identificacion": identity, "tipo_identificacion": "PASAPORTE", "nombre": "Ana", "apellido": "Prueba", "email": "ana@example.com"},
        "rol_id": str(database.role_id), "username": username, "password": "Password123", "usuario_auditoria": "forged",
    }


def employee_payload(database, **changes):
    user = user_payload(database)
    payload = {
        "persona_nueva": user["persona_nueva"], "empresa_id": str(database.company_id),
        "salario": "1234.56", "fecha_ingreso": "2024-01-01", "fecha_nacimiento": "1990-01-01",
        "usuario": {key: user[key] for key in ("username", "password", "rol_id")},
        "usuario_auditoria": "forged",
    }
    return {**payload, **changes}


def persisted_counts(database):
    with Session(database.engine) as session:
        return tuple(len(session.exec(select(model).execution_options(include_inactive=True)).all()) for model in (Persona, Usuario, Empleado))


def provision_employee(database):
    with Session(database.engine) as session:
        employee = EmpleadoService().create(session, employee_payload(database))
        user = session.exec(select(Usuario).where(Usuario.persona_id == employee.persona_id)).one()
        return employee.id, user.id, employee.persona_id


@pytest.mark.parametrize("dto", [UsuarioCreate, EmpleadoCreate])
@pytest.mark.parametrize("alternatives", [{}, {"persona_id": None}, {"persona_id": uuid4(), "persona_nueva": {"identificacion": "OTHER1", "tipo_identificacion": "PASAPORTE", "nombre": "Otra", "apellido": "Persona"}}])
def test_create_union_rejects_both_or_neither(directory_db, dto, alternatives):
    payload = employee_payload(directory_db) if dto is EmpleadoCreate else user_payload(directory_db)
    payload.pop("persona_nueva")
    with pytest.raises(ValidationError):
        dto.model_validate({**payload, **alternatives})
    assert persisted_counts(directory_db) == (1, 1, 0)


def test_employee_composite_projects_person_and_audits_authenticated_actor(directory_db, directory_client):
    response = directory_client.post("/api/v1/empleados", json=employee_payload(directory_db))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["persona"]["nombre"] == "Ana"
    assert body["usuario_auditoria"] == str(directory_db.actor_id)
    assert "password" not in response.text
    with Session(directory_db.engine) as session:
        user = session.exec(select(Usuario).where(Usuario.persona_id == UUID(body["persona_id"]))).one()
        assert user.requiere_cambio_password and verify_password("Password123", user.password_hash)
        assert user.usuario_auditoria == str(directory_db.actor_id)
    assert persisted_counts(directory_db) == (2, 2, 1)


@pytest.mark.parametrize("service_class,payload_factory", [(UsuarioService, user_payload), (EmpleadoService, employee_payload)])
def test_composite_commit_false_is_owned_by_caller(directory_db, monkeypatch, service_class, payload_factory):
    with Session(directory_db.engine) as session:
        commits = []
        monkeypatch.setattr(session, "commit", lambda: commits.append(True))
        service_class().create(session, payload_factory(directory_db), commit=False)
        assert not commits
        session.rollback()
    assert persisted_counts(directory_db) == (1, 1, 0)


@pytest.mark.parametrize("stage", ["user", "employee", "flush", "commit"])
def test_employee_rolls_back_every_persistence_failure(directory_db, monkeypatch, stage):
    with Session(directory_db.engine) as session:
        def fail(*_args, **_kwargs):
            raise RuntimeError(f"failure-{stage}")

        if stage in {"user", "employee"}:
            repository = UsuarioRepository if stage == "user" else EmpleadoRepository
            original = repository.create
            def persist_then_fail(self, target_session, payload):
                original(self, target_session, payload)
                fail()
            monkeypatch.setattr(repository, "create", persist_then_fail)
        elif stage == "commit":
            monkeypatch.setattr(session, "commit", fail)
        else:
            @event.listens_for(session, "before_flush")
            def reject_employee_flush(target_session, _context, _instances):
                if any(isinstance(item, Empleado) for item in target_session.new):
                    fail()
        with pytest.raises(RuntimeError, match=f"failure-{stage}"):
            EmpleadoService().create(session, employee_payload(directory_db))
    assert persisted_counts(directory_db) == (1, 1, 0)


@pytest.mark.parametrize("changes", [{"salario": "-0.01"}, {"salario": "1.001"}, {"salario": "NaN"}, {"fecha_ingreso": str(date.today() + timedelta(days=1))}, {"fecha_salida": "2023-12-31"}, {"fecha_nacimiento": str(date.today())}, {"empresa_id": str(uuid4())}])
def test_labor_validation_rolls_back_contextual_person(directory_db, changes):
    with Session(directory_db.engine) as session, pytest.raises(HTTPException):
        EmpleadoService().create(session, employee_payload(directory_db, **changes))
    assert persisted_counts(directory_db) == (1, 1, 0)


@pytest.mark.parametrize("inactive", [False, True])
def test_employee_prior_user_is_administrative_conflict_without_overwrite(directory_db, inactive):
    with Session(directory_db.engine) as session:
        actor = session.get(Usuario, directory_db.actor_id)
        actor.activo = not inactive
        old_hash = actor.password_hash
        session.commit()
        payload = employee_payload(directory_db)
        payload.pop("persona_nueva")
        payload["persona_id"] = directory_db.person_id
        with pytest.raises(HTTPException) as failure:
            EmpleadoService().create(session, payload)
        assert failure.value.status_code == 409
        assert "administrativa" in failure.value.detail
    with Session(directory_db.engine) as session:
        actor = session.exec(select(Usuario).where(Usuario.id == directory_db.actor_id).execution_options(include_inactive=True)).one()
        assert actor.password_hash == old_hash and actor.activo is not inactive
    assert persisted_counts(directory_db) == (1, 1, 0)


def test_update_dates_use_stored_departure_and_validate_age_salary(directory_db):
    employee_id, _, _ = provision_employee(directory_db)
    with Session(directory_db.engine) as session:
        service = EmpleadoService()
        service.update(session, employee_id, {"fecha_salida": "2024-02-01"})
        for changes in ({"fecha_ingreso": "2024-03-01"}, {"salario": "-1"}, {"fecha_nacimiento": str(date.today())}):
            with pytest.raises(HTTPException) as failure:
                service.update(session, employee_id, changes)
            assert failure.value.status_code == 400
        employee = service.update(session, employee_id, {"salario": "0.00", "fecha_salida": None}, commit=False)
        assert employee.salario == Decimal("0.00")
        session.rollback()


@pytest.mark.parametrize("resource", ["usuarios", "empleados"])
def test_http_identity_and_lifecycle_bypasses_are_explicitly_rejected(directory_db, directory_client, resource):
    employee_id, user_id, _ = provision_employee(directory_db)
    target_id = user_id if resource == "usuarios" else employee_id
    for payload, status_code in (({"persona_id": str(uuid4())}, 409), ({"activo": True}, 422)):
        result = directory_client.put(f"/api/v1/{resource}/{target_id}", json=payload)
        assert result.status_code == status_code, result.text
    if resource == "usuarios":
        assert directory_client.put(f"/api/v1/usuarios/{user_id}", json={"username": "replacement"}).status_code == 409


def test_direct_user_normalizes_username_requires_change_and_never_returns_secret(directory_db, directory_client):
    response = directory_client.post("/api/v1/usuarios", json={**user_payload(directory_db, username="  AnDrea  "), "requiere_cambio_password": False})
    assert response.status_code == 201, response.text
    assert response.json()["username"] == "andrea"
    assert response.json()["requiere_cambio_password"] is True
    assert response.json()["rol_nombre"] == "Administrador"
    assert "password" not in {key for key in response.json() if key != "requiere_cambio_password"}
    assert "password_hash" not in response.text
    assert persisted_counts(directory_db) == (2, 2, 0)
    login = directory_client.post("/api/v1/auth/login", data={"username": " ANDREA ", "password": "Password123"})
    assert login.status_code == 200


@pytest.mark.parametrize("inactive", [False, True])
def test_username_duplicate_including_inactive_rolls_back_new_person(directory_db, inactive):
    with Session(directory_db.engine) as session:
        UsuarioService().create(session, user_payload(directory_db, username="Andrea"))
        user = session.exec(select(Usuario).where(Usuario.username == "andrea")).one()
        user.activo = not inactive
        session.commit()
        with pytest.raises(HTTPException) as failure:
            UsuarioService().create(session, user_payload(directory_db, identity="NEW002", username=" ANDREA "))
        assert failure.value.status_code == 409
    assert persisted_counts(directory_db) == (2, 2, 0)


@pytest.mark.parametrize("service_class,payload_factory", [(UsuarioService, user_payload), (EmpleadoService, employee_payload)])
def test_existing_person_reused_not_overwritten_and_inactive_rejected(directory_db, service_class, payload_factory):
    with Session(directory_db.engine) as session:
        person = Persona(identificacion="NEW001", tipo_identificacion="PASAPORTE", nombre="Original", apellido="Sin cambio")
        session.add(person)
        session.commit()
        person_id = person.id
        created = service_class().create(session, payload_factory(directory_db))
        assert created.persona_id == person_id
        assert session.get(Persona, person_id).nombre == "Original"
        other = Persona(identificacion="NEW002", tipo_identificacion="PASAPORTE", nombre="Inactiva", apellido="Original", activo=False)
        session.add(other)
        session.commit()
        payload = payload_factory(directory_db)
        payload["persona_nueva"]["identificacion"] = "NEW002"
        with pytest.raises(HTTPException) as failure:
            service_class().create(session, payload)
        assert failure.value.status_code == 409
    assert persisted_counts(directory_db)[0] == 3


@pytest.mark.parametrize("resource", ["usuarios", "empleados"])
def test_role_search_projection_pagination_totals_and_historical_state(directory_db, resource):
    provision_employee(directory_db)
    service = UsuarioService() if resource == "usuarios" else EmpleadoService()
    with Session(directory_db.engine) as session:
        items, meta = service.list_paginated(session, q="ana@example.com", limit=1, sort_by="nombre", sort_order="asc")
        assert meta.total == 1 and len(items) == 1
        assert items[0].persona.nombre == "Ana"
        assert "password_hash" not in items[0].model_dump()
        page, meta = service.list_paginated(session, q="ana@example.com", limit=1, offset=1)
        assert not page and meta.total == 1
        service.delete(session, items[0].id)
        active, meta = service.list_paginated(session, q="Ana")
        assert not active and meta.total == 0
        historical, meta = service.list_paginated(session, only_active=False, identificacion=" new001 ", estado="inactivo")
        assert len(historical) == meta.total == 1 and not historical[0].activo
        for bad_order in ({"sort_by": "password_hash"}, {"sort_order": "drop"}, {"estado": "unknown"}):
            with pytest.raises(HTTPException):
                service.list_paginated(session, **bad_order)


def test_company_scope_applies_to_all_employee_operations(directory_db, directory_client):
    employee_id, _, _ = provision_employee(directory_db)
    directory_client.headers["X-Company-Id"] = str(uuid4())
    for method, path, payload in (
        ("post", "/api/v1/empleados", employee_payload(directory_db)),
        ("get", f"/api/v1/empleados/{employee_id}", None),
        ("put", f"/api/v1/empleados/{employee_id}", {"salario": "2000"}),
        ("delete", f"/api/v1/empleados/{employee_id}", None),
        ("post", f"/api/v1/empleados/{employee_id}/reactivar", None),
    ):
        result = directory_client.request(method, path, json=payload)
        assert result.status_code == 403, result.text
    result = directory_client.get("/api/v1/empleados")
    assert result.status_code == 200 and result.json()["meta"]["total"] == 0
    assert persisted_counts(directory_db) == (2, 2, 1)


def test_missing_embedded_person_permission_rolls_back_without_disclosure(directory_db, directory_client):
    with Session(directory_db.engine) as session:
        module = session.exec(select(Modulo).where(Modulo.codigo == "PERSONAS")).one()
        permission = session.exec(select(RolModuloPermiso).where(RolModuloPermiso.modulo_id == module.id)).one()
        permission.puede_crear = False
        session.commit()
    for resource, payload in (("usuarios", user_payload(directory_db)), ("empleados", employee_payload(directory_db))):
        response = directory_client.post(f"/api/v1/{resource}", json=payload)
        assert response.status_code == 403, response.text
    assert persisted_counts(directory_db) == (1, 1, 0)


@pytest.mark.parametrize("resource", ["usuarios", "empleados"])
def test_every_directory_endpoint_enforces_action_permission(directory_db, directory_client, resource):
    with Session(directory_db.engine) as session:
        module = session.exec(select(Modulo).where(Modulo.codigo == resource.upper())).one()
        permission = session.exec(select(RolModuloPermiso).where(RolModuloPermiso.modulo_id == module.id)).one()
        for field in ("puede_leer", "puede_crear", "puede_actualizar", "puede_eliminar"):
            setattr(permission, field, False)
        session.commit()
    target_id = uuid4()
    requests = [
        ("get", "", None), ("get", f"/{target_id}", None),
        ("post", "", user_payload(directory_db) if resource == "usuarios" else employee_payload(directory_db)),
        ("put", f"/{target_id}", {}), ("delete", f"/{target_id}", None), ("post", f"/{target_id}/reactivar", {}),
    ]
    if resource == "usuarios":
        requests.extend([("get", f"/{target_id}/menu", None), ("get", f"/{target_id}/permisos", None), ("post", f"/{target_id}/reset-password", {}), ("post", f"/{target_id}/verify-password", {"password": "Password123"})])
    for method, suffix, payload in requests:
        response = directory_client.request(method, f"/api/v1/{resource}{suffix}", json=payload)
        assert response.status_code == 403, response.text
    assert persisted_counts(directory_db) == (1, 1, 0)


@pytest.mark.parametrize("path", ["direct", "inline", "update", "change", "service", "generator"])
def test_all_password_writes_reject_less_than_eight_characters(directory_db, path):
    with Session(directory_db.engine) as session:
        if path == "direct":
            with pytest.raises(ValidationError):
                UsuarioCreate.model_validate({**user_payload(directory_db), "password": "short"})
        elif path == "inline":
            payload = employee_payload(directory_db)
            payload["usuario"]["password"] = "short"
            with pytest.raises(ValidationError):
                EmpleadoCreate.model_validate(payload)
        elif path == "update":
            with pytest.raises(ValidationError):
                UsuarioUpdate(password="short")
        elif path == "change":
            with pytest.raises(HTTPException):
                UsuarioService().change_password(session, session.get(Usuario, directory_db.actor_id), new_password="short", current_password="Admin12345")
        elif path == "service":
            with pytest.raises(HTTPException):
                UsuarioService().create(session, {**user_payload(directory_db), "password": "short"})
        else:
            with pytest.raises(ValueError):
                UsuarioService()._generate_temp_password(7)
    assert persisted_counts(directory_db) == (1, 1, 0)


@pytest.mark.parametrize("action", ["employee-delete", "user-delete", "logout", "reset"])
def test_access_and_refresh_are_revoked_by_every_lifecycle_action(directory_db, directory_client, action):
    employee_id, user_id, person_id = provision_employee(directory_db)
    access = create_token(user_id, "access", timedelta(minutes=5))
    refresh = create_token(user_id, "refresh", timedelta(days=1))
    user_headers = {"Authorization": f"Bearer {access}"}
    assert directory_client.get("/api/v1/auth/me", headers=user_headers).status_code == 200
    if action == "employee-delete":
        response = directory_client.delete(f"/api/v1/empleados/{employee_id}")
        assert response.status_code == 204
    elif action == "user-delete":
        response = directory_client.delete(f"/api/v1/usuarios/{user_id}")
        assert response.status_code == 204
    elif action == "logout":
        response = directory_client.post("/api/v1/auth/logout", headers=user_headers)
        assert response.status_code == 200
    else:
        response = directory_client.post(f"/api/v1/usuarios/{user_id}/reset-password", json={"usuario_auditoria": "forged"})
        assert response.status_code == 200, response.text
        temporary = response.json()["password_temporal"]
        assert len(temporary) >= 8
        read = directory_client.get(f"/api/v1/usuarios/{user_id}")
        assert read.status_code == 200 and "password_temporal" not in read.text
        login = directory_client.post("/api/v1/auth/login", data={"username": "new-user", "password": temporary})
        assert login.status_code == 200
        change = directory_client.post("/api/v1/auth/change-password", json={"new_password": "Changed123"}, headers={"Authorization": f"Bearer {login.json()['access_token']}"})
        assert change.status_code == 200, change.text
        with Session(directory_db.engine) as session:
            user = session.get(Usuario, user_id)
            assert not user.requiere_cambio_password
            assert verify_password("Changed123", user.password_hash)
            assert user.usuario_auditoria == str(user_id)
    assert directory_client.get("/api/v1/auth/me", headers=user_headers).status_code == 401
    assert directory_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh}).status_code == 401
    with Session(directory_db.engine) as session:
        assert session.get(Persona, person_id).activo
        user = session.exec(select(Usuario).where(Usuario.id == user_id).execution_options(include_inactive=True)).one()
        assert user.sesion_invalidada_en is not None
        employee = session.exec(select(Empleado).where(Empleado.id == employee_id).execution_options(include_inactive=True)).one()
        assert employee.activo is (action != "employee-delete")
    if action.endswith("delete"):
        assert directory_client.post("/api/v1/auth/login", data={"username": "new-user", "password": "Password123"}).status_code == 401


def test_employee_reactivation_preserves_user_revocation_and_historical_ids(directory_db, directory_client):
    employee_id, user_id, person_id = provision_employee(directory_db)
    access = create_token(user_id, "access", timedelta(minutes=5))
    refresh = create_token(user_id, "refresh", timedelta(days=1))
    assert directory_client.delete(f"/api/v1/empleados/{employee_id}").status_code == 204
    response = directory_client.post(f"/api/v1/empleados/{employee_id}/reactivar")
    assert response.status_code == 200, response.text
    assert response.json()["id"] == str(employee_id)
    with Session(directory_db.engine) as session:
        user = session.exec(select(Usuario).where(Usuario.id == user_id).execution_options(include_inactive=True)).one()
        assert not user.activo and user.sesion_invalidada_en is not None
        assert session.get(Persona, person_id).activo
    response = directory_client.post(f"/api/v1/usuarios/{user_id}/reactivar")
    assert response.status_code == 200, response.text
    assert response.json()["id"] == str(user_id)
    assert directory_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"}).status_code == 401
    assert directory_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh}).status_code == 401
    assert directory_client.post("/api/v1/auth/login", data={"username": "new-user", "password": "Password123"}).status_code == 200


def test_user_reactivation_requires_explicit_inactive_employee_decision(directory_db, directory_client):
    employee_id, user_id, _ = provision_employee(directory_db)
    assert directory_client.delete(f"/api/v1/empleados/{employee_id}").status_code == 204
    response = directory_client.post(f"/api/v1/usuarios/{user_id}/reactivar")
    assert response.status_code == 409, response.text
    response = directory_client.post(f"/api/v1/usuarios/{user_id}/reactivar", json={"confirmar_empleado_inactivo": True, "usuario_auditoria": "forged"})
    assert response.status_code == 200, response.text
    assert response.json()["usuario_auditoria"] == str(directory_db.actor_id)
    with Session(directory_db.engine) as session:
        employee = session.exec(select(Empleado).where(Empleado.id == employee_id).execution_options(include_inactive=True)).one()
        assert not employee.activo


@pytest.mark.parametrize("stage", ["employee", "user", "commit"])
def test_employee_deactivation_failure_rolls_back_status_and_invalidation(directory_db, monkeypatch, stage):
    employee_id, user_id, person_id = provision_employee(directory_db)
    with Session(directory_db.engine) as session:
        def fail(*_args, **_kwargs):
            raise RuntimeError("deactivation-failed")
        if stage == "employee":
            monkeypatch.setattr(EmpleadoRepository, "delete", fail)
        elif stage == "user":
            original = UsuarioRepository.update
            def update_then_fail(self, target_session, user, payload):
                original(self, target_session, user, payload)
                fail()
            monkeypatch.setattr(UsuarioRepository, "update", update_then_fail)
        else:
            monkeypatch.setattr(session, "commit", fail)
        with pytest.raises(RuntimeError, match="deactivation-failed"):
            EmpleadoService().delete(session, employee_id)
    with Session(directory_db.engine) as session:
        assert session.get(Empleado, employee_id).activo
        user = session.get(Usuario, user_id)
        assert user.activo and user.sesion_invalidada_en is None
        assert session.get(Persona, person_id).activo


@pytest.mark.parametrize("user_state", ["absent", "inactive"])
def test_employee_deactivation_handles_absent_or_inactive_user(directory_db, user_state):
    employee_id, user_id, person_id = provision_employee(directory_db)
    with Session(directory_db.engine) as session:
        user = session.get(Usuario, user_id)
        if user_state == "absent":
            session.delete(user)
        else:
            user.activo = False
        session.commit()
        assert EmpleadoService().delete(session, employee_id)
        assert session.get(Persona, person_id).activo
        if user_state == "inactive":
            user = session.exec(select(Usuario).where(Usuario.id == user_id).execution_options(include_inactive=True)).one()
            assert user.sesion_invalidada_en is not None


@pytest.mark.parametrize("service_class,target_model", [(UsuarioService, Usuario), (EmpleadoService, Empleado)])
@pytest.mark.parametrize("reference", ["persona", "role_or_company"])
def test_reactivation_rejects_inactive_references(directory_db, service_class, target_model, reference):
    employee_id, user_id, person_id = provision_employee(directory_db)
    target_id = user_id if target_model is Usuario else employee_id
    with Session(directory_db.engine) as session:
        service = service_class()
        service.delete(session, target_id)
        if reference == "persona":
            session.get(Persona, person_id).activo = False
        elif target_model is Usuario:
            session.get(Rol, directory_db.role_id).activo = False
        else:
            session.get(Empresa, directory_db.company_id).activo = False
        session.commit()
        with pytest.raises(HTTPException) as failure:
            service.reactivate(session, target_id)
        assert failure.value.status_code == 409
    with Session(directory_db.engine) as session:
        target = session.exec(select(target_model).where(target_model.id == target_id).execution_options(include_inactive=True)).one()
        assert not target.activo


@pytest.mark.parametrize("operation", ["reset", "logout", "change", "approval"])
def test_security_action_commit_failure_rolls_back(directory_db, monkeypatch, operation):
    with Session(directory_db.engine) as session:
        user = session.get(Usuario, directory_db.actor_id)
        original_hash = user.password_hash
        def fail():
            raise RuntimeError("security-commit-failed")
        monkeypatch.setattr(session, "commit", fail)
        service = UsuarioService()
        with pytest.raises(RuntimeError, match="security-commit-failed"):
            if operation == "reset":
                service.reset_password(session, user.id)
            elif operation == "logout":
                service.invalidate_session(session, user)
            elif operation == "change":
                service.change_password(session, user, current_password="Admin12345", new_password="Changed123")
            else:
                service.set_approval_code(session, user, "1234")
    with Session(directory_db.engine) as session:
        user = session.get(Usuario, directory_db.actor_id)
        assert user.password_hash == original_hash
        assert not user.requiere_cambio_password
        assert user.sesion_invalidada_en is None and user.codigo_aprobacion_hash is None


def test_change_password_requires_current_secret_after_initial_change(directory_db, directory_client):
    response = directory_client.post("/api/v1/auth/change-password", json={"new_password": "Changed123"})
    assert response.status_code == 400
    response = directory_client.post("/api/v1/auth/change-password", json={"current_password": "incorrect", "new_password": "Changed123"})
    assert response.status_code == 400
    response = directory_client.post("/api/v1/auth/change-password", json={"current_password": "Admin12345", "new_password": "Changed123"})
    assert response.status_code == 200


def test_initial_user_without_employee_reactivates_independently(directory_db, directory_client):
    response = directory_client.post("/api/v1/usuarios", json=user_payload(directory_db))
    assert response.status_code == 201
    user_id = response.json()["id"]
    assert directory_client.delete(f"/api/v1/usuarios/{user_id}").status_code == 204
    response = directory_client.post(f"/api/v1/usuarios/{user_id}/reactivar")
    assert response.status_code == 200, response.text
    assert response.json()["id"] == user_id and response.json()["activo"]
    assert persisted_counts(directory_db) == (2, 2, 0)


def test_direct_user_invalid_role_and_persistence_failure_roll_back_person(directory_db, monkeypatch):
    with Session(directory_db.engine) as session:
        with pytest.raises(HTTPException) as failure:
            UsuarioService().create(session, {**user_payload(directory_db), "rol_id": uuid4()})
        assert failure.value.status_code == 404
        original = UsuarioRepository.create
        def persist_then_fail(self, target_session, payload):
            original(self, target_session, payload)
            raise RuntimeError("user-persistence-failed")
        monkeypatch.setattr(UsuarioRepository, "create", persist_then_fail)
        with pytest.raises(RuntimeError, match="user-persistence-failed"):
            UsuarioService().create(session, user_payload(directory_db))
    assert persisted_counts(directory_db) == (1, 1, 0)