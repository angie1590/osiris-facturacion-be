# tests/test_proveedor_sociedad.py
from __future__ import annotations

from uuid import uuid4
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException
from sqlalchemy import exc as sa_exc
from sqlalchemy.exc import IntegrityError

# SUT imports
from osiris.modules.common.proveedor_sociedad.service import ProveedorSociedadService
from osiris.modules.common.proveedor_sociedad.models import (
    ProveedorSociedadCreate,
    ProveedorSociedadUpdate,
)
from osiris.modules.common.proveedor_sociedad.entity import ProveedorSociedad
from osiris.modules.common.persona.entity import Persona
from osiris.modules.sri.tipo_contribuyente.entity import TipoContribuyente
from osiris.utils.validacion_identificacion import ValidacionCedulaRucService


# ---------- helpers ----------

def _mk_cursor(obj):
    cur = MagicMock()
    cur.first.return_value = obj
    return cur


def _mk_session_for_fk(*, persona_exists=True, tc_exists=True, tc_nombre="sociedad privada"):
    """
    Devuelve un MagicMock de session con exec que reconoce selects a
    aux_tipo_contribuyente y tbl_persona, y retorna primero/según el tipo.
    """
    session = MagicMock()

    persona = None
    if persona_exists:
        persona = Persona(
            identificacion="0103523908001",
            tipo_identificacion=None,  # no lo usamos aquí
            nombre="X",
            apellido="Y",
        )
        persona.id = uuid4()
        persona.activo = True

    tc = None
    if tc_exists:
        tc = TipoContribuyente(codigo="99", nombre=tc_nombre)
        tc.activo = True

    def _side_effect(stmt):
        text = str(stmt).lower()
        if "aux_tipo_contribuyente" in text:
            return _mk_cursor(tc)
        if "tbl_persona" in text:
            return _mk_cursor(persona)
        # fallback: cursor vacío
        return _mk_cursor(None)

    session.exec.side_effect = _side_effect
    return session


def _mk_integrity_error(pgcode: str, constraint: str | None = None):
    """
    Crea un IntegrityError de PostgreSQL para mapearlo a 409.
    """
    orig = MagicMock()
    orig.pgcode = pgcode
    orig.diag = MagicMock()
    orig.diag.constraint_name = constraint
    return sa_exc.IntegrityError("stmt", "params", orig)


# ---------- tests ----------

def test_proveedor_sociedad_create_ok(monkeypatch):
    session = _mk_session_for_fk(persona_exists=True, tc_exists=True, tc_nombre="contribuyente regular")

    # Forzamos validador de RUC de sociedad como válido
    monkeypatch.setattr(
        ValidacionCedulaRucService,
        "es_ruc_sociedad_valido",
        lambda r: True,
        raising=False,
    )

    svc = ProveedorSociedadService()
    svc.repo = MagicMock()
    svc.repo.create.side_effect = lambda s, d: ProveedorSociedad(
        ruc=d["ruc"],
        razon_social=d["razon_social"],
        nombre_comercial=d.get("nombre_comercial"),
        direccion=d["direccion"],
        telefono=d.get("telefono"),
        email=d["email"],
        tipo_contribuyente_id=d["tipo_contribuyente_id"],
        persona_contacto_id=d["persona_contacto_id"],
        usuario_auditoria=d["usuario_auditoria"],
    )

    payload = ProveedorSociedadCreate(
        ruc="0190363902001",
        razon_social="OPEN LATINA S.A.",
        nombre_comercial="OpenLatina",
        direccion="Av. Siempre Viva",
        telefono="0999999999",
        email="contacto@openlatina.io",
        tipo_contribuyente_id="99",
        persona_contacto_id=uuid4(),
        usuario_auditoria="tester",
    )

    obj = svc.create(session, payload)
    assert obj.ruc == "0190363902001"
    svc.repo.create.assert_called_once()


def test_proveedor_sociedad_create_tc_no_bloquea(monkeypatch):
    # TC con nombre 'Sociedad Privada' ya NO se bloquea en el servicio
    session = _mk_session_for_fk(
        persona_exists=True,
        tc_exists=True,
        tc_nombre="Sociedad Privada",
    )

    # RUC válido
    monkeypatch.setattr(
        ValidacionCedulaRucService,
        "es_ruc_sociedad_valido",
        lambda r: True,
        raising=False,
    )

    svc = ProveedorSociedadService()
    svc.repo = MagicMock()

    payload = {
        "ruc": "0190363902001",
        "razon_social": "X SA",
        "direccion": "Dir",
        "telefono": "0999999999",
        "email": "ok@email.com",
        "tipo_contribuyente_id": "99",
        "persona_contacto_id": str(uuid4()),
        "usuario_auditoria": "tester",
    }

    # No debe levantar HTTPException
    svc.create(session, payload)

    # Se delega al repositorio
    svc.repo.create.assert_called_once()


def test_proveedor_sociedad_create_ruc_invalido(monkeypatch):
    session = _mk_session_for_fk(persona_exists=True, tc_exists=True, tc_nombre="Contribuyente Regular")

    # Validador indica que NO es un RUC de sociedad válido
    monkeypatch.setattr(
        ValidacionCedulaRucService,
        "es_ruc_sociedad_valido",
        lambda r: False,
        raising=False,
    )

    svc = ProveedorSociedadService()
    svc.repo = MagicMock()

    with pytest.raises(HTTPException) as exc:
        svc.create(
            session,
            {
                "ruc": "0123456789",  # inválido / persona natural
                "razon_social": "X SA",
                "direccion": "Dir",
                "telefono": "0999999999",
                "email": "ok@email.com",
                "tipo_contribuyente_id": "99",
                "persona_contacto_id": str(uuid4()),
                "usuario_auditoria": "tester",
            },
        )
    assert exc.value.status_code == 400
    assert "ruc" in exc.value.detail.lower()


def test_proveedor_sociedad_create_telefono_mal(monkeypatch):
    session = _mk_session_for_fk(persona_exists=True, tc_exists=True, tc_nombre="Contribuyente Regular")

    monkeypatch.setattr(
        ValidacionCedulaRucService,
        "es_ruc_sociedad_valido",
        lambda r: True,
        raising=False,
    )

    svc = ProveedorSociedadService()
    svc.repo = MagicMock()

    with pytest.raises(HTTPException) as exc:
        svc.create(
            session,
            {
                "ruc": "0190363902001",
                "razon_social": "X SA",
                "direccion": "Dir",
                "telefono": "00",  # mal formato
                "email": "ok@email.com",
                "tipo_contribuyente_id": "99",
                "persona_contacto_id": str(uuid4()),
                "usuario_auditoria": "tester",
            },
        )
    assert exc.value.status_code in (400, 422)  # según dónde lo valides
    assert "teléfono" in exc.value.detail.lower() or "10 dígitos" in exc.value.detail.lower()


def test_proveedor_sociedad_create_unique_violation_propagado(monkeypatch):
    """
    El servicio no captura ni mapea IntegrityError; lo deja propagar.
    El mapeo a 409 ocurre en el router/exception handler.
    """
    session = _mk_session_for_fk(
        persona_exists=True,
        tc_exists=True,
        tc_nombre="Contribuyente Regular",
    )

    monkeypatch.setattr(
        ValidacionCedulaRucService,
        "es_ruc_sociedad_valido",
        lambda r: True,
        raising=False,
    )

    svc = ProveedorSociedadService()
    svc.repo = MagicMock()

    def _raise_integrity(_session, data):
        # mismo helper de tus tests
        raise _mk_integrity_error("23505", constraint="uq_tbl_proveedor_sociedad_ruc")

    svc.repo.create.side_effect = _raise_integrity

    with pytest.raises(IntegrityError):
        svc.create(
            session,
            {
                "ruc": "0190363902001",
                "razon_social": "X SA",
                "direccion": "Dir",
                "telefono": "0999999999",
                "email": "ok@email.com",
                "tipo_contribuyente_id": "99",
                "persona_contacto_id": str(uuid4()),
                "usuario_auditoria": "tester",
            },
        )


def test_proveedor_sociedad_create_tc_no_existe(monkeypatch):
    # tc_exists=False -> _check_fk_active_and_exists / validación de negocio debe dar 404
    session = _mk_session_for_fk(persona_exists=True, tc_exists=False)

    monkeypatch.setattr(
        ValidacionCedulaRucService,
        "es_ruc_sociedad_valido",
        lambda r: True,
        raising=False,
    )

    svc = ProveedorSociedadService()
    svc.repo = MagicMock()

    with pytest.raises(HTTPException) as exc:
        svc.create(
            session,
            {
                "ruc": "0190363902001",
                "razon_social": "X SA",
                "direccion": "Dir",
                "telefono": "0999999999",
                "email": "ok@email.com",
                "tipo_contribuyente_id": "XX",  # inexistente
                "persona_contacto_id": str(uuid4()),
                "usuario_auditoria": "tester",
            },
        )

    assert exc.value.status_code == 404
    assert "tipo" in exc.value.detail.lower() and "contribuyente" in exc.value.detail.lower()


def test_proveedor_sociedad_update_valida_tc(monkeypatch):
    """
    En update, si envían tipo_contribuyente_id, se valida FK y la regla de negocio.
    """
    session = _mk_session_for_fk(persona_exists=True, tc_exists=True, tc_nombre="Contribuyente Regular")

    monkeypatch.setattr(
        ValidacionCedulaRucService,
        "es_ruc_sociedad_valido",
        lambda r: True,
        raising=False,
    )

    svc = ProveedorSociedadService()
    svc.repo = MagicMock()

    # Objeto actual
    current = ProveedorSociedad(
        ruc="1790012345001",
        razon_social="X SA",
        nombre_comercial=None,
        direccion="Dir",
        telefono="0999999999",
        email="ok@email.com",
        tipo_contribuyente_id="99",
        persona_contacto_id=uuid4(),
        usuario_auditoria="old",
    )
    current.id = uuid4()
    svc.repo.get.return_value = current
    svc.repo.update.return_value = current

    dto = ProveedorSociedadUpdate(
        tipo_contribuyente_id="98",
        usuario_auditoria="tester",
    )

    res = svc.update(session, current.id, dto)
    assert res is current
    svc.repo.update.assert_called_once()
