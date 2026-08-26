# tests/test_empleado.py
from __future__ import annotations

from datetime import date
from uuid import uuid4
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from osiris.modules.common.empleado.service import EmpleadoService
from osiris.modules.common.empleado.models import (
    EmpleadoCreate,
    EmpleadoUpdate,
    UsuarioInlineCreate,
)
from osiris.modules.common.empleado.entity import Empleado
from osiris.modules.common.empleado.strategy import EmpleadoCrearUsuarioStrategy


# --------------------------
# Helpers
# --------------------------
def _mk_session():
    s = MagicMock()
    s.exec = MagicMock()
    s.add = MagicMock()
    s.commit = MagicMock()
    s.refresh = MagicMock()
    return s


# --------------------------
# Creación: crea usuario + empleado
# --------------------------
def test_empleado_create_crea_usuario_y_empleado(monkeypatch):
    session = _mk_session()

    # Mock strategy: debe crear usuario
    created_user = MagicMock()
    created_user.id = uuid4()

    strategy = EmpleadoCrearUsuarioStrategy(usuario_service=MagicMock())
    strategy.create_user_for_persona = MagicMock(return_value=created_user)

    # Mock repo.create para el empleado
    svc = EmpleadoService(strategy=strategy)
    svc.repo = MagicMock()
    svc.repo.create = MagicMock(return_value=Empleado(
        persona_id=uuid4(),
        empresa_id=uuid4(),
        salario=1000.00,
        fecha_ingreso=date(2024, 1, 1),
        foto=None,
        usuario_auditoria="tester",
    ))

    persona_id = uuid4()
    empresa_id = uuid4()
    payload = {
        "persona_id": persona_id,
        "empresa_id": empresa_id,
        "salario": "1200.00",
        "fecha_ingreso": "2024-01-01",
        "foto": None,
        "usuario": {
            "username": "jdoe",
            "password": "secret123",
            "rol_id": str(uuid4()),
        },
        "usuario_auditoria": "tester",
    }

    emp = svc.create(session, payload)

    # Strategy creada usuario
    strategy.create_user_for_persona.assert_called_once()
    # Se creó empleado por repo
    svc.repo.create.assert_called_once()
    assert isinstance(emp, Empleado)
    assert getattr(emp, "foto", None) is None


def test_empleado_create_con_foto_pasa_a_repo(monkeypatch):
    session = _mk_session()

    strategy = EmpleadoCrearUsuarioStrategy(usuario_service=MagicMock())
    strategy.create_user_for_persona = MagicMock(return_value=MagicMock(id=uuid4()))

    svc = EmpleadoService(strategy=strategy)
    svc.repo = MagicMock()
    svc.repo.create = MagicMock(return_value=Empleado(
        persona_id=uuid4(),
        empresa_id=uuid4(),
        salario=1200.00,
        fecha_ingreso=date(2024, 1, 1),
        foto="https://cdn.example.com/fotos/emp123.jpg",
        usuario_auditoria="tester",
    ))

    payload = {
        "persona_id": str(uuid4()),
        "empresa_id": str(uuid4()),
        "salario": "1200.00",
        "fecha_ingreso": str(date(2024, 1, 1)),
        "foto": "https://cdn.example.com/fotos/emp123.jpg",
        "usuario": {"username": "jdoe", "password": "secret123", "rol_id": str(uuid4())},
        "usuario_auditoria": "tester",
    }

    emp = svc.create(session, payload)
    # Verificar que el payload pasó con foto
    args, kwargs = svc.repo.create.call_args
    data_arg = args[1] if len(args) >= 2 else kwargs.get("data", {})
    assert data_arg.get("foto") == "https://cdn.example.com/fotos/emp123.jpg"
    assert emp.foto == "https://cdn.example.com/fotos/emp123.jpg"


# --------------------------
# Validaciones de modelo (DTO): edad mínima y coherencia de fechas
# --------------------------
def test_empleado_create_valida_edad_minima_por_env(monkeypatch):
    # Forzamos edad mínima a 18
    monkeypatch.setenv("EMP_MIN_AGE", "18")
    hoy = date.today()
    menor_17 = date(hoy.year - 17, hoy.month, hoy.day)

    usuario = UsuarioInlineCreate(
        username="jdoe",
        password="secret123",
        rol_id=uuid4(),
    )

    # Falla por ser menor de 18
    with pytest.raises(ValidationError) as exc:
        EmpleadoCreate(
            persona_id=uuid4(),
            empresa_id=uuid4(),
            salario="1000.00",
            fecha_ingreso=hoy,
            fecha_nacimiento=menor_17,
            usuario=usuario,
        )
    assert "al menos 18 años" in str(exc.value).lower()


def test_empleado_create_valida_fecha_salida_posterior():
    hoy = date.today()
    usuario = UsuarioInlineCreate(
        username="jdoe",
        password="secret123",
        rol_id=uuid4(),
    )
    # fecha_salida <= fecha_ingreso debe fallar
    with pytest.raises(ValidationError) as exc:
        EmpleadoCreate(
            persona_id=uuid4(),
            empresa_id=uuid4(),
            salario="1000.00",
            fecha_ingreso=hoy,
            fecha_salida=hoy,  # igual que ingreso
            usuario=usuario,
        )
    assert "fecha de salida debe ser posterior" in str(exc.value).lower()


# --------------------------
# Update: no cambia persona_id, valida fechas coherentes
# --------------------------
def test_empleado_update_no_cambia_persona_id(monkeypatch):
    session = _mk_session()
    svc = EmpleadoService(strategy=MagicMock())
    svc.repo = MagicMock()

    # Objeto actual
    current = Empleado(
        persona_id=uuid4(),
        empresa_id=uuid4(),
        salario=1500.0,
        fecha_ingreso=date(2024, 1, 1),
        foto=None,
        usuario_auditoria="current",
    )
    current.id = uuid4()
    svc.repo.get.return_value = current

    # Incoming intenta cambiar persona_id (no permitido) y salario
    new_persona_id = uuid4()
    incoming = EmpleadoUpdate(
        salario="2000.00",
        foto="https://cdn.example.com/fotos/emp999.jpg",
        usuario_auditoria="tester",
    )
    # Simulamos que llega persona_id "por error" en dict:
    data_dict = incoming.model_dump(exclude_unset=True)
    data_dict["persona_id"] = str(new_persona_id)

    svc.repo.update.return_value = current

    res = svc.update(session, current.id, data_dict)

    # Service debe haber eliminado persona_id de la actualización
    assert res is current
    assert current.persona_id != new_persona_id

    svc.repo.update.assert_called_once()
    args, kwargs = svc.repo.update.call_args
    update_payload = args[2] if len(args) >= 3 else kwargs.get("data", {})
    assert "persona_id" not in update_payload
    assert update_payload.get("foto") == "https://cdn.example.com/fotos/emp999.jpg"


def test_empleado_update_valida_fecha_salida_vs_ingreso():
    session = _mk_session()
    svc = EmpleadoService(strategy=MagicMock())
    svc.repo = MagicMock()

    current = Empleado(
        persona_id=uuid4(),
        empresa_id=uuid4(),
        salario=1500.0,
        fecha_ingreso=date(2024, 1, 10),
        usuario_auditoria="current",
    )
    current.id = uuid4()
    svc.repo.get.return_value = current

    # Intentamos poner fecha_salida <= fecha_ingreso (debe 400)
    with pytest.raises(HTTPException) as exc:
        svc.update(session, current.id, {"fecha_salida": "2024-01-09"})
    assert exc.value.status_code == 400
    assert "fecha de salida debe ser posterior" in exc.value.detail.lower()


# --------------------------
# Estrategia: valida rol_id antes de crear usuario
# --------------------------
def test_empleado_create_valida_rol_en_strategy(monkeypatch):
    session = _mk_session()

    # Simular que select(Rol.id) -> first() = None => 404
    cursor = MagicMock()
    cursor.first.return_value = None
    session.exec.return_value = cursor

    svc = EmpleadoService()  # usa estrategia real con validación de rol

    payload = {
        "persona_id": str(uuid4()),
        "empresa_id": str(uuid4()),
        "salario": "1000.00",
        "fecha_ingreso": str(date.today()),
        "usuario": {
            "username": "jdoe",
            "password": "secret123",
            "rol_id": str(uuid4()),  # inexistente/inactivo
        },
        "usuario_auditoria": "tester",
    }

    with pytest.raises(HTTPException) as exc:
        svc.create(session, payload)
    assert exc.value.status_code == 404
    assert "rol" in exc.value.detail.lower()


# --------------------------
# Atomicidad: si falla crear empleado, hace rollback de toda la UoW
# --------------------------
def test_empleado_create_rollback_si_falla_repo():
    session = _mk_session()

    fake_user = MagicMock()
    fake_user.id = uuid4()

    strategy = EmpleadoCrearUsuarioStrategy(usuario_service=MagicMock())
    strategy.create_user_for_persona = MagicMock(return_value=fake_user)

    svc = EmpleadoService(strategy=strategy)
    svc.repo = MagicMock()
    svc.repo.create.side_effect = RuntimeError("fallo al crear empleado")

    payload = {
        "persona_id": str(uuid4()),
        "empresa_id": str(uuid4()),
        "salario": "1000.00",
        "fecha_ingreso": str(date.today()),
        "usuario": {"username": "jdoe", "password": "secret123", "rol_id": str(uuid4())},
        "usuario_auditoria": "tester",
    }

    with pytest.raises(RuntimeError):
        svc.create(session, payload)

    session.rollback.assert_called_once()


# --------------------------
# Validación de empresa_id obligatorio
# --------------------------
def test_empleado_create_empresa_id_es_obligatorio():
    """Verifica que empresa_id es obligatorio en EmpleadoCreate"""
    with pytest.raises(ValidationError) as exc:
        EmpleadoCreate(
            persona_id=uuid4(),
            # empresa_id omitido intencionalmente
            salario="1000.00",
            fecha_ingreso=date.today(),
            usuario=UsuarioInlineCreate(
                username="jdoe",
                password="secret123",
                rol_id=uuid4(),
            ),
            usuario_auditoria="tester",
        )

    # Verifica que el error menciona empresa_id
    errors = exc.value.errors()
    assert any(e["loc"] == ("empresa_id",) for e in errors), "Falta validación de empresa_id obligatorio"


def test_empleado_create_valida_empresa_existe(monkeypatch):
    """Verifica que el servicio valida que empresa_id existe en BD"""
    session = _mk_session()

    # Mock strategy para que pase validación de rol y cree usuario
    fake_user = MagicMock()
    fake_user.id = uuid4()

    strategy = EmpleadoCrearUsuarioStrategy(usuario_service=MagicMock())
    strategy.create_user_for_persona = MagicMock(return_value=fake_user)

    svc = EmpleadoService(strategy=strategy)

    # Mock para que BaseService.create llame _validate_fks y falle en empresa_id

    def mock_exec(stmt):
        # Simular que Persona existe pero Empresa no
        stmt_str = str(stmt)
        cursor = MagicMock()

        if "tbl_persona" in stmt_str or "Persona" in stmt_str:
            cursor.first.return_value = MagicMock(id=uuid4())  # Persona existe
        elif "tbl_empresa" in stmt_str or "Empresa" in stmt_str:
            cursor.first.return_value = None  # Empresa NO existe
        else:
            cursor.first.return_value = MagicMock()

        return cursor

    session.exec.side_effect = mock_exec

    payload = {
        "persona_id": str(uuid4()),
        "empresa_id": str(uuid4()),  # UUID que no existe
        "salario": "1000.00",
        "fecha_ingreso": str(date.today()),
        "usuario": {
            "username": "jdoe",
            "password": "secret123",
            "rol_id": str(uuid4()),
        },
        "usuario_auditoria": "tester",
    }

    # Debe lanzar HTTPException 404 por FK no encontrada
    with pytest.raises(HTTPException) as exc:
        svc.create(session, payload)

    assert exc.value.status_code == 404
    assert "empresa" in exc.value.detail.lower()
