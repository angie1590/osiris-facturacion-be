import pytest
from uuid import uuid4
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

# SUT
from osiris.modules.common.proveedor_persona.service import ProveedorPersonaService
from osiris.modules.common.proveedor_persona.entity import ProveedorPersona
from osiris.modules.common.persona.entity import Persona, TipoIdentificacion
from osiris.modules.sri.tipo_contribuyente.entity import TipoContribuyente


# -------------------- helpers --------------------
def _cursor_with_first(obj):
    cur = MagicMock()
    cur.first.return_value = obj
    return cur


def _mk_persona(
    *,
    id_=None,
    identificacion="0123456789001",
    tipo_identificacion=TipoIdentificacion.RUC,
):
    p = MagicMock(spec=Persona)
    p.id = id_ or uuid4()
    p.identificacion = identificacion
    p.tipo_identificacion = tipo_identificacion
    return p


def _mk_tc(*, codigo="01", nombre="Persona Natural"):
    tc = MagicMock(spec=TipoContribuyente)
    tc.codigo = codigo
    # algunos esquemas usan 'nombre', otros 'descripcion'; ponemos ambas
    tc.nombre = nombre
    tc.descripcion = nombre
    return tc


# -------------------- tests: CREATE --------------------
def test_proveedor_persona_create_ok(monkeypatch):
    session = MagicMock()

    persona = _mk_persona()
    tc = _mk_tc(codigo="01", nombre="Persona Natural")

    # Orden de llamadas en el service.create:
    # 1) FK persona (BaseService)
    # 2) FK tipo contribuyente (BaseService)
    # 3) persona (regla ruc natural)
    # 4) tipo contribuyente (regla permitido)
    session.exec.side_effect = [
        _cursor_with_first(persona),
        _cursor_with_first(tc),
        _cursor_with_first(persona),
        _cursor_with_first(tc),
    ]

    # Validador RUC natural => True
    monkeypatch.setattr(
        "osiris.utils.validacion_identificacion.ValidacionCedulaRucService.es_ruc_persona_natural_valido",
        lambda r: True,
        raising=True,
    )

    svc = ProveedorPersonaService()
    svc.repo = MagicMock()
    created = ProveedorPersona(nombre_comercial="X")
    svc.repo.create.return_value = created

    payload = {
        "persona_id": str(persona.id),
        "tipo_contribuyente_id": tc.codigo,
        "nombre_comercial": "OpenLatina",
        "usuario_auditoria": "tester",
    }

    res = svc.create(session, payload)
    assert res is created
    svc.repo.create.assert_called_once()
    # se espera que BaseRepository haga commit/refresh internamente


def test_proveedor_persona_create_rechaza_tc_prohibido(monkeypatch):
    session = MagicMock()
    persona = _mk_persona()
    tc_prohibido = _mk_tc(codigo="02", nombre="Sociedad Anónima")

    session.exec.side_effect = [
        _cursor_with_first(persona),
        _cursor_with_first(tc_prohibido),
        _cursor_with_first(persona),
        _cursor_with_first(tc_prohibido),
    ]

    monkeypatch.setattr(
        "osiris.utils.validacion_identificacion.ValidacionCedulaRucService.es_ruc_persona_natural_valido",
        lambda r: True,
        raising=True,
    )

    svc = ProveedorPersonaService()
    svc.repo = MagicMock()

    with pytest.raises(HTTPException) as exc:
        svc.create(
            session,
            {
                "persona_id": str(persona.id),
                "tipo_contribuyente_id": tc_prohibido.codigo,
                "usuario_auditoria": "tester",
            },
        )

    assert exc.value.status_code == 400
    assert "no es válido" in exc.value.detail.lower()
    svc.repo.create.assert_not_called()


def test_proveedor_persona_create_rechaza_si_no_ruc_natural(monkeypatch):
    session = MagicMock()
    # Persona con RUC pero validador dice que NO es persona natural
    persona = _mk_persona()
    tc = _mk_tc()

    session.exec.side_effect = [
        _cursor_with_first(persona),
        _cursor_with_first(tc),
        _cursor_with_first(persona),
        _cursor_with_first(tc),
    ]

    monkeypatch.setattr(
        "osiris.utils.validacion_identificacion.ValidacionCedulaRucService.es_ruc_persona_natural_valido",
        lambda r: False,
        raising=True,
    )

    svc = ProveedorPersonaService()
    svc.repo = MagicMock()

    with pytest.raises(HTTPException) as exc:
        svc.create(
            session,
            {
                "persona_id": str(persona.id),
                "tipo_contribuyente_id": tc.codigo,
                "usuario_auditoria": "tester",
            },
        )

    assert exc.value.status_code == 400
    assert "persona natural" in exc.value.detail.lower()
    svc.repo.create.assert_not_called()


def test_proveedor_persona_create_tc_no_existe(monkeypatch):
    session = MagicMock()
    persona = _mk_persona()

    session.exec.side_effect = [
        _cursor_with_first(persona),
        _cursor_with_first(None),   # FK TC (no existe) → 404 en BaseService o en regla
    ]

    monkeypatch.setattr(
        "osiris.utils.validacion_identificacion.ValidacionCedulaRucService.es_ruc_persona_natural_valido",
        lambda r: True,
        raising=True,
    )

    svc = ProveedorPersonaService()
    svc.repo = MagicMock()

    with pytest.raises(HTTPException) as exc:
        svc.create(
            session,
            {
                "persona_id": str(persona.id),
                "tipo_contribuyente_id": "XX",
                "usuario_auditoria": "tester",
            },
        )

    assert exc.value.status_code == 404
    svc.repo.create.assert_not_called()


def test_proveedor_persona_create_unicidad_persona_repo_409():
    """
    Simulamos que el repo mapea IntegrityError a HTTP 409 (unicidad persona_id).
    """
    session = MagicMock()
    svc = ProveedorPersonaService()
    svc.repo = MagicMock()
    svc.repo.create.side_effect = HTTPException(status_code=409, detail="persona_id duplicado")

    # Saltamos hits a DB de FKs y reglas para concentrar en el 409 del repo
    with patch.object(ProveedorPersonaService, "_check_fk_active_and_exists"):
        with patch.object(ProveedorPersonaService, "_assert_persona_ruc_natural"):
            with patch.object(ProveedorPersonaService, "_assert_tipo_contribuyente_permitido"):
                with pytest.raises(HTTPException) as exc:
                    svc.create(
                        session,
                        {
                            "persona_id": str(uuid4()),
                            "tipo_contribuyente_id": "01",
                            "usuario_auditoria": "tester",
                        },
                    )

    assert exc.value.status_code == 409
    assert "duplicado" in exc.value.detail.lower()


# -------------------- tests: UPDATE --------------------
def test_proveedor_persona_update_no_cambia_persona_id(monkeypatch):
    session = MagicMock()
    svc = ProveedorPersonaService()
    svc.repo = MagicMock()

    current = ProveedorPersona(
        nombre_comercial="A",
        persona_id=uuid4(),
        tipo_contribuyente_id="01",
        usuario_auditoria="old",
    )
    current.id = uuid4()
    svc.repo.get.return_value = current
    svc.repo.update.return_value = current

    # Intento de cambiar persona_id debe ser IGNORADO
    data = {
        "persona_id": str(uuid4()),           # <-- debe ser eliminado por el service
        "nombre_comercial": "Nuevo",
        "usuario_auditoria": "tester",
    }

    # No enviamos tc_id, así que no se harán validaciones de tc en update
    res = svc.update(session, current.id, data)
    assert res is current

    # Verificamos que persona_id NO fue enviado al repo.update
    args, kwargs = svc.repo.update.call_args
    sent_data = args[2] if len(args) >= 3 else kwargs.get("data") or kwargs
    assert "persona_id" not in sent_data


def test_proveedor_persona_update_valida_tc_si_llega(monkeypatch):
    session = MagicMock()
    svc = ProveedorPersonaService()
    svc.repo = MagicMock()

    current = ProveedorPersona(
        nombre_comercial="A",
        persona_id=uuid4(),
        tipo_contribuyente_id="01",
        usuario_auditoria="old",
    )
    current.id = uuid4()
    svc.repo.get.return_value = current
    svc.repo.update.return_value = current

    _mk_persona()
    tc_ok = _mk_tc(codigo="03", nombre="Persona Natural")

    # En update, si viene tipo_contribuyente_id,
    # el service llama _check_fk_active_and_exists y la regla de tc permitido.
    session.exec.side_effect = [
        _cursor_with_first(tc_ok),     # fk_map tc (exists)
        _cursor_with_first(tc_ok),     # regla tc permitido
    ]

    monkeypatch.setattr(
        "osiris.utils.validacion_identificacion.ValidacionCedulaRucService.es_ruc_persona_natural_valido",
        lambda r: True,
        raising=True,
    )

    res = svc.update(
        session,
        current.id,
        {"tipo_contribuyente_id": tc_ok.codigo, "usuario_auditoria": "tester"},
    )

    assert res is current
    svc.repo.update.assert_called_once()


def test_proveedor_persona_update_tc_no_existe(monkeypatch):
    session = MagicMock()
    svc = ProveedorPersonaService()
    svc.repo = MagicMock()

    current = ProveedorPersona(
        nombre_comercial="A",
        persona_id=uuid4(),
        tipo_contribuyente_id="01",
        usuario_auditoria="old",
    )
    current.id = uuid4()
    svc.repo.get.return_value = current

    # fk tipo inexistente
    session.exec.side_effect = [
        _cursor_with_first(None),
    ]

    with pytest.raises(HTTPException) as exc:
        svc.update(
            session,
            current.id,
            {"tipo_contribuyente_id": "XX", "usuario_auditoria": "tester"},
        )

    assert exc.value.status_code == 404
    svc.repo.update.assert_not_called()
