# tests/unit/test_persona_unit.py
from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy import create_engine
from sqlmodel import Session

from osiris.modules.common.persona.models import (
    PersonaCreate,
    PersonaUpdate,
    TipoIdentificacion,
)
from osiris.modules.common.persona.entity import Persona
from osiris.modules.common.persona.service import PersonaService
from osiris.modules.common.persona.repository import PersonaRepository
from osiris.modules.common.persona.composition import PersonaReference, resolve_persona


class _Diag:
    def __init__(self, constraint_name=None, column_name=None, table_name=None):
        self.constraint_name = constraint_name
        self.column_name = column_name
        self.table_name = table_name


class _PGOrig:
    def __init__(self, pgcode, constraint=None, column=None, table=None, text=""):
        self.pgcode = pgcode
        self.diag = _Diag(constraint, column, table)
        self._text = text

    def __str__(self):
        return self._text or f"PG error {self.pgcode}"


def _mk_integrity_error(pgcode, *, constraint=None, column=None, table=None, text=""):
    return IntegrityError("stmt", {}, _PGOrig(pgcode, constraint, column, table, text))


# ============================================================
# Validaciones de PersonaCreate (cédula / ruc natural / pasaporte)
# ============================================================


def test_persona_create_cedula_valida_ok():
    with patch(
        "osiris.utils.validacion_identificacion.ValidacionCedulaRucService.es_cedula_valida",
        return_value=True,
    ):
        dto = PersonaCreate(
            identificacion="0104815956",
            tipo_identificacion=TipoIdentificacion.CEDULA,
            nombre="Juan",
            apellido="Pérez",
            usuario_auditoria="tester",
        )
        assert dto.tipo_identificacion is TipoIdentificacion.CEDULA


def test_persona_create_cedula_invalida_falla():
    with patch(
        "osiris.utils.validacion_identificacion.ValidacionCedulaRucService.es_cedula_valida",
        return_value=False,
    ):
        with pytest.raises(ValidationError) as exc:
            PersonaCreate(
                identificacion="0000000000",
                tipo_identificacion=TipoIdentificacion.CEDULA,
                nombre="Juan",
                apellido="Pérez",
                usuario_auditoria="tester",
            )
        assert "cédula" in str(exc.value).lower()


def test_persona_create_ruc_persona_natural_ok():
    with patch(
        "osiris.utils.validacion_identificacion.ValidacionCedulaRucService.es_ruc_persona_natural_valido",
        return_value=True,
    ):
        dto = PersonaCreate(
            identificacion="0104815956001",
            tipo_identificacion=TipoIdentificacion.RUC,
            nombre="Ana",
            apellido="López",
            usuario_auditoria="tester",
        )
        assert dto.tipo_identificacion is TipoIdentificacion.RUC


def test_persona_create_ruc_no_natural_rechazado():
    # Sólo se acepta RUC de persona natural → aquí forzamos False
    with patch(
        "osiris.utils.validacion_identificacion.ValidacionCedulaRucService.es_ruc_persona_natural_valido",
        return_value=False,
    ):
        with pytest.raises(ValidationError) as exc:
            PersonaCreate(
                identificacion="1790012345001",  # típico de sociedad → debe fallar
                tipo_identificacion=TipoIdentificacion.RUC,
                nombre="Carlos",
                apellido="Mora",
                usuario_auditoria="tester",
            )
        assert "persona natural" in str(exc.value).lower()


def test_persona_create_pasaporte_corto_falla():
    with pytest.raises(ValidationError) as exc:
        PersonaCreate(
            identificacion="AB12",  # < 5
            tipo_identificacion=TipoIdentificacion.PASAPORTE,
            nombre="Lina",
            apellido="Gómez",
            usuario_auditoria="tester",
        )
    assert "pasaporte" in str(exc.value).lower()


# ============================================================
# Validaciones de PersonaUpdate
# ============================================================


def test_persona_update_ident_y_tipo_deben_ir_juntos():
    # Enviar solo identificacion sin tipo → debe fallar
    with pytest.raises(ValidationError) as exc:
        PersonaUpdate(
            identificacion="0123456789",
            usuario_auditoria="tester",
        )
    assert "debes enviar también el tipo" in str(exc.value).lower()


def test_persona_update_ruc_natural_ok():
    with patch(
        "osiris.utils.validacion_identificacion.ValidacionCedulaRucService.es_ruc_persona_natural_valido",
        return_value=True,
    ):
        dto = PersonaUpdate(
            identificacion="0104815956001",
            tipo_identificacion=TipoIdentificacion.RUC,
            usuario_auditoria="tester",
        )
        assert dto.identificacion.endswith("001")


def test_persona_update_ruc_no_natural_falla():
    with patch(
        "osiris.utils.validacion_identificacion.ValidacionCedulaRucService.es_ruc_persona_natural_valido",
        return_value=False,
    ):
        with pytest.raises(ValidationError) as exc:
            PersonaUpdate(
                identificacion="1790012345001",
                tipo_identificacion=TipoIdentificacion.RUC,
                usuario_auditoria="tester",
            )
        assert "persona natural" in str(exc.value).lower()


# ============================================================
# Service: create → 409 si la identificación ya existe
# ============================================================


def test_persona_service_create_ident_duplicada_da_409_via_repository():
    session = MagicMock()
    session.add = MagicMock()
    session.commit.side_effect = _mk_integrity_error(
        "23505",
        constraint="uq_tbl_persona_identificacion",
        column="identificacion",
        table="tbl_persona",
    )
    session.refresh = MagicMock()

    svc = PersonaService()  # usa repo real (con handler de IntegrityError)

    payload = {
        "identificacion": "0123456789",
        "tipo_identificacion": "CEDULA",
        "nombre": "Juan",
        "apellido": "Pérez",
        "usuario_auditoria": "tester",
    }

    with pytest.raises(HTTPException) as exc:
        svc.create(session, payload)

    assert exc.value.status_code == 409
    assert (
        "ya existe" in exc.value.detail.lower()
        or "duplic" in exc.value.detail.lower()
        or "únic" in exc.value.detail.lower()
    )


def test_persona_service_create_ok_llama_repo_create():
    session = MagicMock()

    # No existe la identificación previa
    not_exists_cursor = MagicMock()
    not_exists_cursor.first.return_value = None
    session.exec.return_value = not_exists_cursor

    svc = PersonaService()
    svc.repo = MagicMock()
    svc.repo.create.return_value = "CREATED"

    payload = {
        "identificacion": "0123456789",
        "tipo_identificacion": TipoIdentificacion.CEDULA,
        "nombre": "Juan",
        "apellido": "Pérez",
        "usuario_auditoria": "tester",
    }

    out = svc.create(session, payload)
    assert out == "CREATED"
    svc.repo.create.assert_called_once()


# ============================================================
# Repository: delete lógico (marca activo=False, commit)
# ============================================================


def test_persona_repository_delete_logico():
    session = MagicMock()
    repo = PersonaRepository()

    obj = Persona(
        identificacion="0123456789",
        tipo_identificacion=TipoIdentificacion.CEDULA,
        nombre="Pedro",
        apellido="Suárez",
        usuario_auditoria="tester",
        activo=True,
    )

    ok = repo.delete(session, obj)

    assert ok is True
    assert obj.activo is False
    session.add.assert_called_once_with(obj)
    session.flush.assert_called_once()
    session.commit.assert_not_called()
    # No exigimos refresh por ser DELETE 204 y no tener triggers de UPDATE
    session.refresh.assert_not_called()


def test_persona_passport_normalization_in_create_update_and_service():
    payload = {
        "identificacion": " ab123 ",
        "tipo_identificacion": "PASAPORTE",
        "nombre": " Ana ",
        "apellido": " Perez ",
        "usuario_auditoria": "test",
    }
    created = PersonaCreate(**payload)
    updated = PersonaUpdate(**payload)
    assert created.identificacion == updated.identificacion == "AB123"
    assert created.nombre == created.nombre.strip()
    session = MagicMock()
    repository = MagicMock()
    PersonaService(repository).create(session, payload)
    assert repository.create.call_args.args[1]["identificacion"] == "AB123"


def test_persona_server_search_pagination_and_inactive_views():
    engine = create_engine("sqlite://")
    Persona.__table__.create(engine)
    try:
        with Session(engine) as session:
            session.add_all(
                [
                    Persona(
                        identificacion="AA111",
                        tipo_identificacion="PASAPORTE",
                        nombre="Ana",
                        apellido="Uno",
                        email="ana@example.com",
                        usuario_auditoria="test",
                    ),
                    Persona(
                        identificacion=" ab123 ",
                        tipo_identificacion="PASAPORTE",
                        nombre="Zoe",
                        apellido="Dos",
                        telefono="0999999999",
                        usuario_auditoria="test",
                        activo=False,
                    ),
                ]
            )
            session.commit()
            repo = PersonaRepository()
            items, total = repo.list(session, limit=1)
            assert total == 1 and items[0].nombre == "Ana"
            items, total = repo.list(session, only_active=False, identificacion="Ab123")
            assert total == 1 and items[0].nombre == "Zoe" and items[0].activo is False
            items, total = repo.list(session, q="example.com")
            assert total == 1 and items[0].nombre == "Ana"
            items, total = repo.list(
                session, only_active=False, q="0999999999", estado="inactivo"
            )
            assert total == 1 and items[0].nombre == "Zoe"
            items, total = repo.list(
                session, only_active=False, limit=1, offset=1, sort_by="nombre"
            )
            assert total == 2 and items[0].nombre == "Zoe"
    finally:
        engine.dispose()


def test_persona_service_rejects_partial_identity_update():
    with pytest.raises(HTTPException) as exc:
        PersonaService().update(MagicMock(), uuid4(), {"identificacion": "AB123"})
    assert exc.value.status_code == 422


def test_composite_persona_reference_is_exclusive():
    draft = {
        "identificacion": "AB123",
        "tipo_identificacion": "PASAPORTE",
        "nombre": "Ana",
        "apellido": "Perez",
    }
    assert PersonaReference(persona_nueva=draft).persona_nueva.identificacion == "AB123"
    assert PersonaReference(persona_id=uuid4()).persona_nueva is None
    for payload in [{}, {"persona_id": uuid4(), "persona_nueva": draft}]:
        with pytest.raises(ValidationError):
            PersonaReference(**payload)


def test_composite_persona_reuses_existing_without_overwriting_and_rejects_inactive():
    engine = create_engine("sqlite://")
    Persona.__table__.create(engine)
    draft = {
        "identificacion": " ab123 ",
        "tipo_identificacion": "PASAPORTE",
        "nombre": "Propuesta",
        "apellido": "Nueva",
    }
    try:
        with Session(engine) as session:
            original = Persona(
                identificacion="AB123",
                tipo_identificacion="PASAPORTE",
                nombre="Original",
                apellido="Persistido",
                usuario_auditoria="test",
            )
            session.add(original)
            session.commit()
            payload = resolve_persona(
                session, {"persona_nueva": draft, "tipo_cliente_id": uuid4()}
            )
            assert payload["persona_id"] == original.id
            assert "persona_nueva" not in payload
            assert original.nombre == "Original"
            original.activo = False
            session.commit()
            with pytest.raises(HTTPException) as exc:
                resolve_persona(session, {"persona_nueva": draft})
            assert exc.value.status_code == 409
            assert exc.value.detail["persona_id"] == str(original.id)
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "role",
    ["cliente", "proveedor_persona", "empleado", "usuario", "proveedores_sociedad"],
)
def test_persona_deactivation_rejects_every_active_dependency(role):
    session = MagicMock()
    service = PersonaService(repo=MagicMock())
    person = Persona(
        identificacion="AB123",
        tipo_identificacion="PASAPORTE",
        nombre="Ana",
        apellido="Perez",
    )
    dependency = MagicMock()
    dependency.id = uuid4()
    dependency.activo = True
    dependency.razon_social = "Sociedad de prueba"
    keys = [
        "cliente",
        "proveedor_persona",
        "empleado",
        "usuario",
        "proveedores_sociedad",
    ]
    cursor = MagicMock()
    cursor.first.return_value = person
    dependency_results = []
    for key in keys:
        result = MagicMock()
        result.all.return_value = [dependency] if key == role else []
        dependency_results.append(result)
    session.exec.side_effect = [cursor, cursor, *dependency_results]
    with pytest.raises(HTTPException) as exc:
        service.delete(session, person.id)
    assert exc.value.status_code == 409
    assert exc.value.detail["dependencias_activas"][0]["recurso"] == role
    assert person.activo is True
    service.repo.delete.assert_not_called()
    session.rollback.assert_called_once()


def test_persona_generic_update_cannot_bypass_reactivation():
    with pytest.raises(HTTPException) as exc:
        PersonaService().update(MagicMock(), uuid4(), {"activo": True})
    assert exc.value.status_code == 422


def test_persona_dto_rejects_internal_lifecycle_and_audit_fields():
    for field in ("activo", "created_by", "updated_by", "creado_en", "actualizado_en"):
        with pytest.raises(ValidationError):
            PersonaUpdate.model_validate({field: True})
