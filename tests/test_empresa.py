# tests/unit/test_empresa_unit.py
from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from osiris.modules.common.empresa.models import (
    EmpresaCreate,
    EmpresaRegimenModoRules,
    EmpresaUpdate,
)
from osiris.modules.common.empresa.entity import (
    Empresa,
    ModoEmisionEmpresa,
    RegimenTributario,
    _registrar_auditoria_regimen_modo_after_update,
)
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.empresa.repository import EmpresaRepository
from osiris.modules.common.empresa.service import EmpresaService


# =======================
# DTO validations (Pydantic) – mock del validador de RUC
# =======================

def test_empresa_create_valida_usa_validador_ruc_ok():
    with patch(
        "osiris.modules.common.empresa.models.ValidacionCedulaRucService.es_identificacion_valida",
        return_value=True,
    ):
        dto = EmpresaCreate(
            razon_social="Comercial ABC",
            nombre_comercial="ABC S.A.",
            ruc="1104680138001",
            direccion_matriz="Av. Siempre Viva 123",
            telefono="0987654321",
            obligado_contabilidad=True,
            tipo_contribuyente_id="01",
            usuario_auditoria="tester",
        )
        assert dto.ruc == "1104680138001"
        assert dto.tipo_contribuyente_id == "01"
        assert dto.regimen == RegimenTributario.GENERAL
        assert dto.modo_emision == ModoEmisionEmpresa.ELECTRONICO


def test_empresa_create_ruc_invalido_lanza_validationerror():
    with patch(
        "osiris.modules.common.empresa.models.ValidacionCedulaRucService.es_identificacion_valida",
        return_value=False,
    ):
        with pytest.raises(ValidationError):
            EmpresaCreate(
                razon_social="Empresa XYZ",
                nombre_comercial="XYZ",
                ruc="0000000000000",
                direccion_matriz="Calle Falsa 123",
                telefono="022345678",
                obligado_contabilidad=False,
                tipo_contribuyente_id="01",
                usuario_auditoria="tester",
            )


def test_empresa_update_ruc_none_no_valida_y_es_permitido():
    # ruc es opcional en update; si va None no debe validarse
    # (no hace falta patch del validador)
    dto = EmpresaUpdate(ruc=None, telefono="022345678")
    assert dto.ruc is None
    assert dto.telefono == "022345678"


def test_empresa_update_regimen_modo_invalido_lanza_http_400():
    with pytest.raises(HTTPException) as exc:
        EmpresaUpdate(
            regimen=RegimenTributario.GENERAL,
            modo_emision=ModoEmisionEmpresa.NOTA_VENTA_FISICA,
        )
    assert exc.value.status_code == 400


def test_empresa_regimen_modo_rules_invalido_para_regimen_general():
    with pytest.raises(ValidationError):
        EmpresaRegimenModoRules(
            regimen=RegimenTributario.GENERAL,
            modo_emision=ModoEmisionEmpresa.NOTA_VENTA_FISICA,
        )


# =======================
# Repository (Session mock)
# =======================

def test_empresa_repository_create_desde_dict_instancia_y_persiste():
    session = MagicMock()
    repo = EmpresaRepository()

    payload = {
        "razon_social": "Mi Empresa",
        "nombre_comercial": "Mi Empresa Cía",
        "ruc": "1104680138001",
        "direccion_matriz": "Av. 123",
        "telefono": "022345678",
        "obligado_contabilidad": True,
        "regimen": RegimenTributario.GENERAL,
        "modo_emision": ModoEmisionEmpresa.ELECTRONICO,
        "tipo_contribuyente_id": "01",
        "usuario_auditoria": "tester",
        "activo": True,
    }

    created = repo.create(session, payload)
    assert isinstance(created, Empresa)
    assert created.razon_social == "Mi Empresa"
    session.add.assert_called_once()
    session.flush.assert_called_once()
    session.commit.assert_not_called()
    session.refresh.assert_not_called()


def test_empresa_repository_update_parcial_no_pisa_campos_no_enviados():
    session = MagicMock()
    repo = EmpresaRepository()

    db_obj = Empresa(
        razon_social="Original SA",
        nombre_comercial=None,
        ruc="1104680138001",
        direccion_matriz="Dir 1",
        telefono=None,
        obligado_contabilidad=False,
        regimen=RegimenTributario.GENERAL,
        modo_emision=ModoEmisionEmpresa.ELECTRONICO,
        tipo_contribuyente_id="01",
        usuario_auditoria="tester",
    )

    partial = EmpresaUpdate(
        nombre_comercial="Nuevo NC",  # no enviamos razon_social
        telefono="022345678",
    )

    updated = repo.update(session, db_obj, partial)

    assert updated.razon_social == "Original SA"     # se mantiene
    assert updated.nombre_comercial == "Nuevo NC"    # cambia
    assert updated.telefono == "022345678"           # cambia

    add_calls = session.add.call_args_list
    assert any(call.args and call.args[0] is db_obj for call in add_calls)
    assert any(isinstance(call.args[0], AuditLog) for call in add_calls if call.args)
    audit_entries = [call.args[0] for call in add_calls if call.args and isinstance(call.args[0], AuditLog)]
    assert len(audit_entries) == 1
    audit = audit_entries[0]
    assert audit.estado_anterior["nombre_comercial"] is None
    assert audit.estado_nuevo["nombre_comercial"] == "Nuevo NC"
    assert audit.estado_anterior["regimen"] == "GENERAL"
    assert audit.estado_nuevo["modo_emision"] == "ELECTRONICO"
    session.flush.assert_called_once()
    session.commit.assert_not_called()
    session.refresh.assert_not_called()


def test_empresa_repository_delete_logico_activo_a_false():
    session = MagicMock()
    repo = EmpresaRepository()

    db_obj = Empresa(
        razon_social="Para Borrar",
        nombre_comercial=None,
        ruc="1104680138001",
        direccion_matriz="Dir",
        regimen=RegimenTributario.GENERAL,
        modo_emision=ModoEmisionEmpresa.ELECTRONICO,
        tipo_contribuyente_id="01",
        usuario_auditoria="tester",
        activo=True,
    )

    ok = repo.delete(session, db_obj)
    assert ok is True
    assert db_obj.activo is False
    session.add.assert_called_once_with(db_obj)
    session.delete.assert_not_called()
    session.flush.assert_called_once()
    session.commit.assert_not_called()


# =======================
# Service (repo mock)
# =======================

def test_empresa_service_update_not_found_devuelve_none():
    repo = MagicMock()
    repo.get.return_value = None

    s = EmpresaService()
    s.repo = repo

    out = s.update(MagicMock(), item_id=uuid4(), data={"razon_social": "X"})
    assert out is None
    repo.update.assert_not_called()


def test_empresa_service_update_found_llama_repo_update():
    repo = MagicMock()
    repo.get.return_value = Empresa(
        razon_social="Empresa",
        nombre_comercial="Empresa",
        ruc="1104680138001",
        direccion_matriz="Dir",
        regimen=RegimenTributario.GENERAL,
        modo_emision=ModoEmisionEmpresa.ELECTRONICO,
        tipo_contribuyente_id="01",
        usuario_auditoria="tester",
    )
    repo.update.return_value = "UPDATED"

    s = EmpresaService()
    s.repo = repo

    out = s.update(MagicMock(), item_id=uuid4(), data={"razon_social": "Y"})
    assert out == "UPDATED"
    repo.update.assert_called_once()


def test_empresa_service_update_rechaza_nota_venta_fisica_para_regimen_general():
    repo = MagicMock()
    repo.get.return_value = Empresa(
        razon_social="Empresa",
        nombre_comercial="Empresa",
        ruc="1104680138001",
        direccion_matriz="Dir",
        regimen=RegimenTributario.GENERAL,
        modo_emision=ModoEmisionEmpresa.ELECTRONICO,
        tipo_contribuyente_id="01",
        usuario_auditoria="tester",
    )

    s = EmpresaService()
    s.repo = repo

    with pytest.raises(HTTPException) as exc:
        s.update(MagicMock(), item_id=uuid4(), data={"modo_emision": ModoEmisionEmpresa.NOTA_VENTA_FISICA})

    assert exc.value.status_code == 400
    repo.update.assert_not_called()


def test_empresa_service_create_rechaza_nota_venta_fisica_para_regimen_general():
    session = MagicMock()
    s = EmpresaService()

    with pytest.raises(HTTPException) as exc:
        s.create(
            session,
            {
                "razon_social": "Empresa",
                "ruc": "1104680138001",
                "direccion_matriz": "Dir",
                "tipo_contribuyente_id": "01",
                "usuario_auditoria": "tester",
                "regimen": RegimenTributario.GENERAL,
                "modo_emision": ModoEmisionEmpresa.NOTA_VENTA_FISICA,
            },
        )

    assert exc.value.status_code == 400


def test_empresa_service_list_paginated_retorna_items_y_meta():
    repo = MagicMock()
    repo.list.return_value = (["e1", "e2"], 7)

    s = EmpresaService()
    s.repo = repo

    items, meta = s.list_paginated(MagicMock(), limit=2, offset=4, only_active=True)
    assert items == ["e1", "e2"]
    assert meta.total == 7
    assert meta.limit == 2
    assert meta.offset == 4
    assert meta.has_more is True


def test_empresa_create_con_logo_opcional():
    """Verifica que el campo logo sea opcional y acepte valores válidos"""
    with patch(
        "osiris.modules.common.empresa.models.ValidacionCedulaRucService.es_identificacion_valida",
        return_value=True,
    ):
        # Sin logo
        dto_sin_logo = EmpresaCreate(
            razon_social="Empresa Sin Logo",
            nombre_comercial="Sin Logo SA",
            ruc="1104680138001",
            direccion_matriz="Calle Principal 456",
            telefono="0987654321",
            tipo_contribuyente_id="01",
            usuario_auditoria="tester",
        )
        assert dto_sin_logo.logo is None
        assert dto_sin_logo.regimen == RegimenTributario.GENERAL
        assert dto_sin_logo.modo_emision == ModoEmisionEmpresa.ELECTRONICO

        # Con logo (URL o path)
        dto_con_logo = EmpresaCreate(
            razon_social="Empresa Con Logo",
            nombre_comercial="Con Logo SA",
            ruc="1104680138001",
            direccion_matriz="Calle Principal 456",
            telefono="0987654321",
            logo="https://ejemplo.com/logo.png",
            tipo_contribuyente_id="01",
            usuario_auditoria="tester",
        )
        assert dto_con_logo.logo == "https://ejemplo.com/logo.png"


def test_empresa_update_puede_actualizar_logo():
    """Verifica que el logo se pueda actualizar parcialmente"""
    session = MagicMock()
    repo = EmpresaRepository()

    db_obj = Empresa(
        razon_social="Empresa Test",
        nombre_comercial="Test SA",
        ruc="1104680138001",
        direccion_matriz="Dir Test",
        regimen=RegimenTributario.GENERAL,
        modo_emision=ModoEmisionEmpresa.ELECTRONICO,
        tipo_contribuyente_id="01",
        usuario_auditoria="tester",
        logo=None,  # Sin logo inicialmente
    )

    # Actualizar solo el logo
    partial = EmpresaUpdate(logo="https://nuevo-logo.com/logo.jpg")
    updated = repo.update(session, db_obj, partial)

    assert updated.logo == "https://nuevo-logo.com/logo.jpg"
    assert updated.razon_social == "Empresa Test"  # otros campos se mantienen

    add_calls = session.add.call_args_list
    assert any(call.args and call.args[0] is db_obj for call in add_calls)
    assert any(isinstance(call.args[0], AuditLog) for call in add_calls if call.args)
    session.flush.assert_called_once()
    session.commit.assert_not_called()
    session.refresh.assert_not_called()


def test_empresa_after_update_listener_registra_before_after_json():
    connection = MagicMock()
    target = Empresa(
        razon_social="Empresa",
        ruc="1104680138001",
        direccion_matriz="Dir",
        tipo_contribuyente_id="01",
        usuario_auditoria="tester",
    )

    history_changed = MagicMock()
    history_changed.deleted = [RegimenTributario.GENERAL]
    history_changed.added = [RegimenTributario.RIMPE_NEGOCIO_POPULAR]
    history_changed.has_changes.return_value = True

    history_same = MagicMock()
    history_same.deleted = []
    history_same.added = []
    history_same.has_changes.return_value = False

    state = MagicMock()
    state.attrs = {
        "regimen": MagicMock(history=history_changed),
        "modo_emision": MagicMock(history=history_same),
    }

    with patch("osiris.modules.common.empresa.entity.sa_inspect", return_value=state):
        _registrar_auditoria_regimen_modo_after_update(MagicMock(), connection, target)

    connection.execute.assert_called_once()
    payload = connection.execute.call_args.args[0].compile().params
    assert payload["before_json"]["regimen"] == "GENERAL"
    assert payload["after_json"]["regimen"] == "RIMPE_NEGOCIO_POPULAR"
    assert payload["before_json"]["modo_emision"] == "ELECTRONICO"
    assert payload["after_json"]["modo_emision"] == "ELECTRONICO"


def test_empresa_after_update_listener_no_registra_si_no_hay_cambio():
    connection = MagicMock()
    target = Empresa(
        razon_social="Empresa",
        ruc="1104680138001",
        direccion_matriz="Dir",
        tipo_contribuyente_id="01",
        usuario_auditoria="tester",
    )

    history_same = MagicMock()
    history_same.deleted = []
    history_same.added = []
    history_same.has_changes.return_value = False

    state = MagicMock()
    state.attrs = {
        "regimen": MagicMock(history=history_same),
        "modo_emision": MagicMock(history=history_same),
    }

    with patch("osiris.modules.common.empresa.entity.sa_inspect", return_value=state):
        _registrar_auditoria_regimen_modo_after_update(MagicMock(), connection, target)

    connection.execute.assert_not_called()
