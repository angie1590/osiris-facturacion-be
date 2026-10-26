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


def _commercial_queries(session, persona, catalog):
    def query(statement):
        text = str(statement)
        if "tbl_proveedor_persona" in text:
            return _cursor_with_first(None)
        if "tbl_persona" in text:
            return _cursor_with_first(persona)
        return _cursor_with_first(catalog)
    session.exec.side_effect = query


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
    p.activo = True
    return p


def _mk_tc(*, codigo="01", nombre="Persona Natural"):
    tc = MagicMock(spec=TipoContribuyente)
    tc.codigo = codigo
    # algunos esquemas usan 'nombre', otros 'descripcion'; ponemos ambas
    tc.nombre = nombre
    tc.descripcion = nombre
    tc.activo = True
    tc.aplica_persona_natural = codigo in {"01", "03", "04"}
    tc.aplica_sociedad = codigo in {"02", "04", "05"}
    return tc


# -------------------- tests: CREATE --------------------
def test_proveedor_persona_create_ok(monkeypatch):
    session = MagicMock()

    persona = _mk_persona()
    tc = _mk_tc(codigo="01", nombre="Persona Natural")

    _commercial_queries(session, persona, tc)

    # Validador RUC natural => True
    monkeypatch.setattr(
        "osiris.utils.validacion_identificacion.ValidacionCedulaRucService.es_ruc_persona_natural_valido",
        lambda r: True,
        raising=True,
    )

    svc = ProveedorPersonaService()
    svc.repo = MagicMock(model=ProveedorPersona)
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

    _commercial_queries(session, persona, tc_prohibido)

    monkeypatch.setattr(
        "osiris.utils.validacion_identificacion.ValidacionCedulaRucService.es_ruc_persona_natural_valido",
        lambda r: True,
        raising=True,
    )

    svc = ProveedorPersonaService()
    svc.repo = MagicMock(model=ProveedorPersona)

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

    _commercial_queries(session, persona, tc)

    monkeypatch.setattr(
        "osiris.utils.validacion_identificacion.ValidacionCedulaRucService.es_ruc_persona_natural_valido",
        lambda r: False,
        raising=True,
    )

    svc = ProveedorPersonaService()
    svc.repo = MagicMock(model=ProveedorPersona)

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

    _commercial_queries(session, persona, None)

    monkeypatch.setattr(
        "osiris.utils.validacion_identificacion.ValidacionCedulaRucService.es_ruc_persona_natural_valido",
        lambda r: True,
        raising=True,
    )

    svc = ProveedorPersonaService()
    svc.repo = MagicMock(model=ProveedorPersona)

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
    svc.repo = MagicMock(model=ProveedorPersona)
    svc.repo.create.side_effect = HTTPException(status_code=409, detail="persona_id duplicado")

    # Saltamos hits a DB de FKs y reglas para concentrar en el 409 del repo
    with patch.object(ProveedorPersonaService, "_check_fk_active_and_exists"), \
            patch.object(ProveedorPersonaService, "_check_duplicate"), \
            patch("osiris.domain.directory_service.resolve_persona", side_effect=lambda session, data, **kwargs: data):
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

    data = {
        "persona_id": str(uuid4()),
        "nombre_comercial": "Nuevo",
        "usuario_auditoria": "tester",
    }

    with pytest.raises(HTTPException) as error:
        svc.update(session, current.id, data)
    assert error.value.status_code == 409
    assert "inmutable" in error.value.detail
    svc.repo.update.assert_not_called()
    session.rollback.assert_called_once()


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


def test_proveedor_persona_applicability_does_not_depend_on_catalog_name():
    session = MagicMock()
    catalog = _mk_tc(codigo="03", nombre="Sociedad: etiqueta editada")
    session.exec.return_value = _cursor_with_first(catalog)
    ProveedorPersonaService()._assert_tipo_contribuyente_permitido(session, catalog.codigo)
    catalog.aplica_persona_natural = False
    catalog.nombre = "Persona Natural"
    with pytest.raises(HTTPException) as exc:
        ProveedorPersonaService()._assert_tipo_contribuyente_permitido(session, catalog.codigo)
    assert exc.value.status_code == 400


def test_proveedor_persona_rejects_inactive_catalog():
    session = MagicMock()
    catalog = _mk_tc()
    catalog.activo = False
    session.exec.return_value = _cursor_with_first(catalog)
    with pytest.raises(HTTPException) as exc:
        ProveedorPersonaService()._assert_tipo_contribuyente_permitido(session, catalog.codigo)
    assert exc.value.status_code == 409


def test_proveedor_persona_fk_map_validates_inactive_persona():
    session = MagicMock()
    persona = _mk_persona()
    persona.activo = False
    session.exec.return_value = _cursor_with_first(persona)
    with pytest.raises(HTTPException) as exc:
        ProveedorPersonaService()._check_fk_active_and_exists(session, {"persona_id": persona.id})
    assert exc.value.status_code == 409
