from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from itertools import product
from typing import Any, cast
from unittest.mock import patch
from uuid import uuid4

import pytest
import sqlalchemy as sa
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, select

from osiris.core.audit import record_domain_change
from osiris.core.audit_context import (
    get_current_user_id,
    reset_current_user_id,
    set_current_user_id,
)
from osiris.core.auth import oauth2_scheme
from osiris.core.catalog_permissions import (
    CATALOG_PERMISSIONS,
    CatalogOperation,
    CatalogPermission,
    catalog_permission,
    require_catalog_permission,
)
from osiris.core.db import get_session
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.modulo.entity import Modulo
from osiris.modules.common.rol.entity import Rol
from osiris.modules.common.rol_modulo_permiso.entity import RolModuloPermiso
from osiris.modules.common.rol_modulo_permiso.service import RolModuloPermisoService
from osiris.modules.common.usuario.entity import Usuario


EXPECTED: dict[CatalogOperation, tuple[CatalogPermission, ...]] = {
    "read_categories": (("CATEGORIAS", "leer"),),
    "create_category": (("CATEGORIAS", "crear"),),
    "update_category": (("CATEGORIAS", "actualizar"),),
    "move_category": (("CATEGORIAS", "actualizar"),),
    "deactivate_category": (("CATEGORIAS", "eliminar"),),
    "reactivate_category": (("CATEGORIAS", "actualizar"),),
    "read_category_attributes": (("CATEGORIAS", "leer"), ("ATRIBUTOS", "leer")),
    "configure_mapping": (("CATEGORIAS", "actualizar"), ("ATRIBUTOS", "leer")),
    "assign_attribute": (("CATEGORIAS", "actualizar"), ("ATRIBUTOS", "leer")),
    "override_mapping": (("CATEGORIAS", "actualizar"), ("ATRIBUTOS", "leer")),
    "remove_mapping": (("CATEGORIAS", "actualizar"), ("ATRIBUTOS", "leer")),
    "reactivate_mapping": (("CATEGORIAS", "actualizar"), ("ATRIBUTOS", "leer")),
    "backfill_mapping": (("CATEGORIAS", "actualizar"), ("ATRIBUTOS", "leer")),
    "preview_mapping": (("CATEGORIAS", "actualizar"), ("ATRIBUTOS", "leer")),
    "create_and_assign_attribute": (
        ("CATEGORIAS", "actualizar"),
        ("ATRIBUTOS", "leer"),
        ("ATRIBUTOS", "crear"),
    ),
    "read_attributes": (("ATRIBUTOS", "leer"),),
    "create_attribute": (("ATRIBUTOS", "crear"),),
    "update_attribute": (("ATRIBUTOS", "actualizar"),),
    "deactivate_attribute": (("ATRIBUTOS", "eliminar"),),
    "reactivate_attribute": (("ATRIBUTOS", "actualizar"),),
    "undo_attribute_change": (("ATRIBUTOS", "actualizar"),),
    "annotate_attribute_unit": (("ATRIBUTOS", "actualizar"),),
    "preview_attribute_update": (("ATRIBUTOS", "actualizar"),),
    "preview_attribute_deactivation": (("ATRIBUTOS", "eliminar"),),
    "read_units": (("UNIDADES", "leer"),),
    "create_unit": (("UNIDADES", "crear"),),
    "update_unit": (("UNIDADES", "actualizar"),),
    "deactivate_unit": (("UNIDADES", "eliminar"),),
    "reactivate_unit": (("UNIDADES", "actualizar"),),
}


@dataclass
class CatalogFixture:
    engine: Engine
    session: Session
    user: Usuario
    role: Rol
    probe: sa.Table
    writes: list[str] = field(default_factory=list)
    callers: list[tuple[str, str | None]] = field(default_factory=list)

    def grant(self, permissions: tuple[CatalogPermission, ...]) -> None:
        by_module: dict[str, dict[str, bool]] = {}
        for module, action in permissions:
            by_module.setdefault(module, {})[f"puede_{action}"] = True
        for code, flags in by_module.items():
            module_record = Modulo(codigo=code, nombre=code)
            self.session.add(module_record)
            self.session.add(
                RolModuloPermiso(rol_id=self.role.id, modulo_id=module_record.id, **flags)
            )
        self.session.commit()
        self.writes.clear()

    def app(self, operation: CatalogOperation) -> FastAPI:
        app = FastAPI()
        app.dependency_overrides[get_session] = lambda: self.session

        @app.post("/probe")
        def caller(
            payload: dict[str, str],
            actor: Usuario = Depends(catalog_permission(operation)),
        ) -> dict[str, str]:
            self.callers.append((str(actor.id), get_current_user_id()))
            entity_id = uuid4()
            self.session.execute(self.probe.insert().values(id=str(entity_id), actor=str(actor.id)))
            record_domain_change(
                self.session,
                entity=self.probe.name,
                entity_id=entity_id,
                action="UPDATE_CATEGORY_ATTRIBUTE",
                before={},
                after={"actor": str(actor.id), "nombre": payload.get("nombre", "test")},
            )
            self.session.flush()
            return {"actor": str(actor.id)}

        return app


@pytest.fixture
def catalog() -> Iterator[CatalogFixture]:
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @sa.event.listens_for(engine, "connect")
    def sqlite_connect(connection: Any, _record: Any) -> None:
        connection.isolation_level = None

    @sa.event.listens_for(engine, "begin")
    def sqlite_begin(connection: sa.Connection) -> None:
        connection.exec_driver_sql("BEGIN")

    for model in (Rol, Usuario, Modulo, RolModuloPermiso, AuditLog):
        cast(sa.Table, sa.inspect(model).local_table).create(engine)
    probe = sa.Table(
        "catalog_permission_probe",
        sa.MetaData(),
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("actor", sa.String, nullable=False),
    )
    probe.create(engine)
    role = Rol(nombre="Operador")
    user = Usuario(
        persona_id=uuid4(), rol_id=role.id, username="catalog-test", password_hash="unused"
    )
    with engine.begin() as connection:
        connection.execute(cast(sa.Table, sa.inspect(Rol).local_table).insert(), role.model_dump())
        connection.execute(
            cast(sa.Table, sa.inspect(Usuario).local_table).insert(), user.model_dump()
        )
    with Session(engine) as session:
        fixture = CatalogFixture(engine, session, user, role, probe)

        @sa.event.listens_for(engine, "before_cursor_execute")
        def capture_writes(
            _connection: sa.Connection,
            _cursor: Any,
            statement: str,
            _parameters: Any,
            _context: Any,
            _executemany: bool,
        ) -> None:
            if statement.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE"}:
                fixture.writes.append(statement)

        yield fixture
    engine.dispose()


CASES = [
    pytest.param(
        operation, tuple(granted), all(enabled), id=f"{operation}-{''.join(map(str, bits))}"
    )
    for operation, requirements in EXPECTED.items()
    for bits in product((0, 1), repeat=len(requirements))
    for enabled in [tuple(bool(bit) for bit in bits)]
    for granted in [[permission for permission, allowed in zip(requirements, enabled) if allowed]]
]


def test_matrix_is_explicit_and_immutable() -> None:
    assert dict(CATALOG_PERMISSIONS) == EXPECTED
    with pytest.raises(TypeError):
        cast(Any, CATALOG_PERMISSIONS)["read_units"] = ()
    with pytest.raises(KeyError):
        catalog_permission(cast(CatalogOperation, "unknown"))


@pytest.mark.parametrize(("operation", "permissions", "allowed"), CASES)
def test_dispatcher_requires_every_effective_grant_without_denial_writes(
    catalog: CatalogFixture,
    operation: CatalogOperation,
    permissions: tuple[CatalogPermission, ...],
    allowed: bool,
) -> None:
    catalog.grant(permissions)
    app = catalog.app(operation)
    with patch(
        "osiris.core.auth.decode_token",
        return_value={"sub": str(catalog.user.id), "type": "access"},
    ):
        with TestClient(app) as client:
            response = client.post(
                "/probe",
                headers={"Authorization": "Bearer test-boundary"},
                json={"usuario_auditoria": str(uuid4())},
            )
    assert response.status_code == (200 if allowed else 403)
    if allowed:
        assert catalog.callers == [(str(catalog.user.id), str(catalog.user.id))]
    else:
        assert catalog.callers == []
        assert catalog.writes == []
        assert catalog.session.scalar(sa.select(sa.func.count()).select_from(catalog.probe)) == 0
        assert catalog.session.exec(select(AuditLog)).all() == []


@pytest.mark.parametrize(
    "state",
    [
        "role_missing",
        "role_inactive",
        "user_missing",
        "user_inactive",
        "module_missing",
        "module_inactive",
        "grant_missing",
        "grant_inactive",
    ],
)
def test_inactive_or_missing_authorization_records_deny(
    catalog: CatalogFixture, state: str
) -> None:
    catalog.grant(EXPECTED["update_attribute"])
    model = {"role": Rol, "user": Usuario, "module": Modulo, "grant": RolModuloPermiso}[
        state.split("_")[0]
    ]
    table = cast(sa.Table, sa.inspect(model).local_table)
    catalog.session.execute(
        table.delete() if state.endswith("missing") else table.update().values(activo=False)
    )
    catalog.session.commit()
    catalog.writes.clear()
    with pytest.raises(HTTPException) as error:
        require_catalog_permission(catalog.session, catalog.user.id, "update_attribute")
    assert error.value.status_code == 403
    assert catalog.writes == []


def test_non_admin_and_unrelated_permissions_never_bypass(catalog: CatalogFixture) -> None:
    catalog.grant((("ATRIBUTOS", "leer"), ("UNIDADES", "actualizar")))
    with pytest.raises(HTTPException) as error:
        require_catalog_permission(catalog.session, catalog.user.id, "update_attribute")
    assert error.value.status_code == 403
    assert catalog.writes == []


def test_active_admin_bypasses_catalog_grants_even_when_modules_are_missing(
    catalog: CatalogFixture,
) -> None:
    catalog.session.execute(sa.update(Rol).values(nombre="  ADMIN  "))
    catalog.session.commit()
    for operation in CATALOG_PERMISSIONS:
        assert (
            require_catalog_permission(catalog.session, catalog.user.id, operation).id
            == catalog.user.id
        )


def test_admin_effective_permissions_include_missing_catalog_modules(
    catalog: CatalogFixture,
) -> None:
    catalog.session.execute(sa.update(Rol).values(nombre="Administrador"))
    catalog.session.commit()

    permissions = RolModuloPermisoService().obtener_permisos_por_rol(
        catalog.session, catalog.role.id
    )

    by_code = {permission.codigo: permission for permission in permissions}
    for code in ("CATEGORIAS", "ATRIBUTOS", "UNIDADES"):
        assert code in by_code
        assert by_code[code].puede_leer
        assert by_code[code].puede_crear
        assert by_code[code].puede_actualizar
        assert by_code[code].puede_eliminar


def test_inactive_admin_role_does_not_report_effective_permissions(
    catalog: CatalogFixture,
) -> None:
    module = Modulo(codigo="CATEGORIAS", nombre="Categorías")
    catalog.session.add(module)
    catalog.session.flush()
    catalog.session.add(
        RolModuloPermiso(
            rol_id=catalog.role.id,
            modulo_id=module.id,
            puede_leer=True,
            puede_crear=True,
            puede_actualizar=True,
            puede_eliminar=True,
        )
    )
    catalog.session.get(Rol, catalog.role.id).activo = False
    catalog.session.commit()

    permissions = RolModuloPermisoService().obtener_permisos_por_rol(
        catalog.session, catalog.role.id
    )

    category_permission = next(item for item in permissions if item.codigo == "CATEGORIAS")
    assert not category_permission.puede_leer
    assert not category_permission.puede_crear
    assert not category_permission.puede_actualizar
    assert not category_permission.puede_eliminar


def test_non_admin_with_permission_is_allowed(catalog: CatalogFixture) -> None:
    catalog.grant(EXPECTED["update_attribute"])
    catalog.session.execute(sa.update(Rol).values(nombre="Operador"))
    catalog.session.commit()
    assert (
        require_catalog_permission(catalog.session, catalog.user.id, "update_attribute").id
        == catalog.user.id
    )


@pytest.mark.parametrize("allowed", [False, True])
def test_helper_never_flushes_commits_or_rolls_back_outer_transaction(
    catalog: CatalogFixture, allowed: bool
) -> None:
    catalog.grant(EXPECTED["update_attribute"] if allowed else ())
    outer_id = str(uuid4())
    catalog.session.execute(catalog.probe.insert().values(id=outer_id, actor="outer"))
    catalog.writes.clear()
    pending = Rol(nombre="Pending outer work")
    catalog.session.add(pending)
    with (
        patch.object(catalog.session, "commit", wraps=catalog.session.commit) as commit,
        patch.object(catalog.session, "rollback", wraps=catalog.session.rollback) as rollback,
        patch.object(catalog.session, "flush", wraps=catalog.session.flush) as flush,
    ):
        if allowed:
            require_catalog_permission(catalog.session, catalog.user.id, "update_attribute")
        else:
            with pytest.raises(HTTPException):
                require_catalog_permission(catalog.session, catalog.user.id, "update_attribute")
        commit.assert_not_called()
        rollback.assert_not_called()
        flush.assert_not_called()
    assert pending in catalog.session.new
    assert catalog.writes == []
    with catalog.session.no_autoflush:
        assert catalog.session.scalar(sa.select(catalog.probe.c.id)) == outer_id
    catalog.session.rollback()
    assert catalog.session.get(Rol, pending.id) is None
    assert catalog.session.scalar(sa.select(sa.func.count()).select_from(catalog.probe)) == 0


def test_authenticated_actor_reaches_caller_and_real_audit_event(catalog: CatalogFixture) -> None:
    catalog.grant(EXPECTED["configure_mapping"])
    forged_actor = str(uuid4())
    app = catalog.app("configure_mapping")
    with patch(
        "osiris.core.auth.decode_token",
        return_value={"sub": str(catalog.user.id), "type": "access"},
    ):
        with TestClient(app) as client:
            response = client.post(
                "/probe",
                headers={"Authorization": "Bearer test-boundary", "X-User-Id": forged_actor},
                json={"usuario_auditoria": forged_actor, "actor": forged_actor},
            )
    assert response.status_code == 200
    actor = str(catalog.user.id)
    assert response.json() == {"actor": actor}
    assert catalog.callers == [(actor, actor)]
    audit_event = catalog.session.exec(select(AuditLog)).one()
    assert audit_event.accion == "UPDATE_CATEGORY_ATTRIBUTE"
    assert audit_event.usuario_id == actor
    assert audit_event.usuario_auditoria == actor
    assert audit_event.created_by == actor
    assert audit_event.updated_by == actor
    assert audit_event.estado_nuevo["actor"] == actor
    assert catalog.session.scalar(sa.select(catalog.probe.c.actor)) == actor
    catalog.session.rollback()
    assert catalog.session.exec(select(AuditLog)).all() == []
    assert catalog.session.scalar(sa.select(sa.func.count()).select_from(catalog.probe)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("caller_fails", [False, True])
async def test_dependency_restores_outer_audit_context(
    catalog: CatalogFixture, caller_fails: bool
) -> None:
    catalog.grant(EXPECTED["read_attributes"])
    outer_actor = "outer-context"
    token = set_current_user_id(outer_actor)
    guard = catalog_permission("read_attributes")(usuario=catalog.user, session=catalog.session)
    try:
        actor = await anext(guard)
        assert actor.id == catalog.user.id
        assert get_current_user_id() == str(catalog.user.id)
        if caller_fails:
            with pytest.raises(RuntimeError, match="caller failure"):
                await guard.athrow(RuntimeError("caller failure"))
        else:
            await guard.aclose()
        assert get_current_user_id() == outer_actor
    finally:
        await guard.aclose()
        reset_current_user_id(token)


def test_anonymous_request_does_not_reach_caller(catalog: CatalogFixture) -> None:
    catalog.grant(EXPECTED["update_attribute"])
    with TestClient(catalog.app("update_attribute")) as client:
        response = client.post("/probe", json={"usuario_auditoria": str(catalog.user.id)})
    assert response.status_code == 401
    assert catalog.writes == []
    assert catalog.callers == []


@pytest.mark.parametrize("token_type", ["refresh", "invalid"])
def test_non_access_subject_is_not_a_catalog_actor(
    catalog: CatalogFixture, token_type: str
) -> None:
    catalog.grant(EXPECTED["update_attribute"])
    app = catalog.app("update_attribute")
    app.dependency_overrides[oauth2_scheme] = lambda: "test-boundary"
    with patch(
        "osiris.core.auth.decode_token",
        return_value={"sub": str(catalog.user.id), "type": token_type},
    ):
        with TestClient(app) as client:
            response = client.post("/probe", json={})
    assert response.status_code == 401
    assert catalog.writes == []
    assert catalog.callers == []
