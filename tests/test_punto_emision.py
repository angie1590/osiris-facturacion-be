# tests/unit/test_punto_emision_unit.py
from __future__ import annotations

from uuid import uuid4
from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.punto_emision.models import PuntoEmisionCreate
from osiris.modules.common.punto_emision.entity import (
    PuntoEmision,
    PuntoEmisionSecuencial,
    TipoDocumentoSRI,
)
from osiris.modules.common.punto_emision.service import PuntoEmisionService
from osiris.modules.common.punto_emision.repository import PuntoEmisionRepository
from osiris.modules.common.rol.entity import Rol
from osiris.modules.common.usuario.entity import Usuario


# =======================
# DTOs: validaciones
# =======================

def test_punto_emision_create_ok():
    dto = PuntoEmisionCreate(
        codigo="002",
        descripcion="Caja 2",
        secuencial_actual=5,
        sucursal_id=uuid4(),
        usuario_auditoria="tester",
    )
    assert dto.codigo == "002"
    assert dto.secuencial_actual == 5


def test_punto_emision_create_codigo_invalido_falla():
    with pytest.raises(ValidationError):
        PuntoEmisionCreate(
            codigo="22",  # debe ser 3 chars
            descripcion="PE",
            sucursal_id=uuid4(),
            usuario_auditoria="tester",
        )


# =======================
# Service: create valida FK de sucursal
# =======================

def test_punto_emision_service_create_sucursal_not_found_404():
    session = MagicMock()
    # check sucursal -> None
    session.exec.return_value.first.return_value = None

    svc = PuntoEmisionService()
    svc.repo = MagicMock()

    payload = {
        "codigo": "010",
        "descripcion": "Caja 10",
        "sucursal_id": uuid4(),
    }

    with pytest.raises(HTTPException) as exc:
        svc.create(session, payload)

    assert exc.value.status_code == 404
    assert "Sucursal" in exc.value.detail
    svc.repo.create.assert_not_called()


def test_punto_emision_service_create_ok_llama_repo_create():
    session = MagicMock()
    # sucursal existe
    first = MagicMock()
    first.first.return_value = object()
    session.exec.side_effect = [first]

    svc = PuntoEmisionService()
    svc.repo = MagicMock()
    svc.repo.create.return_value = "PE_CREATED"

    payload = {
        "codigo": "012",
        "descripcion": "Caja 12",
        "sucursal_id": uuid4(),
    }

    out = svc.create(session, payload)
    assert out == "PE_CREATED"
    svc.repo.create.assert_called_once()


# =======================
# Service: list_by_sucursal (paginado)
# =======================

def test_punto_emision_service_list_by_sucursal_retorna_items_y_meta():
    session = MagicMock()
    svc = PuntoEmisionService()
    svc.repo = MagicMock()
    svc.repo.list.return_value = (["p1", "p2", "p3"], 7)

    items, meta = svc.list_by_sucursal(
        session,
        sucursal_id=uuid4(),
        limit=3,
        offset=3,
        only_active=True,
    )

    assert items == ["p1", "p2", "p3"]
    assert meta.total == 7
    assert meta.limit == 3
    assert meta.offset == 3
    assert meta.has_more is True  # 7 > 6


# =======================
# Repository: delete lógico
# =======================

def test_punto_emision_repository_delete_logico():
    session = MagicMock()
    repo = PuntoEmisionRepository()

    obj = PuntoEmision(
        codigo="014",
        descripcion="PE 14",
        sucursal_id=uuid4(),
        usuario_auditoria="tester",
        activo=True,
    )
    ok = repo.delete(session, obj)
    assert ok is True
    assert obj.activo is False
    session.add.assert_called_once_with(obj)
    session.flush.assert_called_once()
    session.commit.assert_not_called()
    # opcional: garantizar que no refrescamos
    session.refresh.assert_not_called()


def test_punto_emision_service_obtener_siguiente_secuencial_for_update_y_padding_9():
    session = MagicMock()
    svc = PuntoEmisionService()

    pe_id = uuid4()
    punto_emision = PuntoEmision(
        id=pe_id,
        codigo="015",
        descripcion="PE 15",
        sucursal_id=uuid4(),
        usuario_auditoria="tester",
        activo=True,
    )
    session.get.return_value = punto_emision

    secuencial = PuntoEmisionSecuencial(
        punto_emision_id=pe_id,
        tipo_documento=TipoDocumentoSRI.FACTURA,
        secuencial_actual=9,
        usuario_auditoria="tester",
        activo=True,
    )
    locked = MagicMock()
    locked.one.return_value = secuencial
    session.exec.return_value = locked

    siguiente = svc.obtener_siguiente_secuencial(
        session,
        punto_emision_id=pe_id,
        tipo_documento=TipoDocumentoSRI.FACTURA,
        usuario_auditoria="u-1",
    )

    assert siguiente == "000000010"
    assert secuencial.secuencial_actual == 10
    assert secuencial.usuario_auditoria == "u-1"
    stmt = session.exec.call_args.args[0]
    assert getattr(stmt, "_for_update_arg", None) is not None
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(secuencial)


def test_punto_emision_service_ajuste_manual_registra_auditoria_detallada():
    session = MagicMock()
    svc = PuntoEmisionService()

    pe_id = uuid4()
    user_id = uuid4()
    punto_emision = PuntoEmision(
        id=pe_id,
        codigo="016",
        descripcion="PE 16",
        sucursal_id=uuid4(),
        usuario_auditoria="tester",
        activo=True,
    )
    session.get.return_value = punto_emision

    admin = Usuario(
        id=user_id,
        persona_id=uuid4(),
        rol_id=uuid4(),
        username="admin",
        password_hash="hash",
        requiere_cambio_password=False,
        usuario_auditoria="tester",
        activo=True,
    )
    rol = Rol(id=admin.rol_id, nombre="ADMIN", descripcion="Admin", usuario_auditoria="tester", activo=True)
    first = MagicMock()
    first.first.return_value = (admin, rol)
    session.exec.side_effect = [first]

    secuencial = PuntoEmisionSecuencial(
        punto_emision_id=pe_id,
        tipo_documento=TipoDocumentoSRI.RETENCION,
        secuencial_actual=22,
        usuario_auditoria="tester",
        activo=True,
    )
    second = MagicMock()
    second.one.return_value = secuencial
    session.exec.side_effect = [first, second]

    with patch("osiris.modules.common.punto_emision.service.verificar_permiso", return_value=True):
        updated = svc.ajustar_secuencial_manual(
            session,
            punto_emision_id=pe_id,
            tipo_documento=TipoDocumentoSRI.RETENCION,
            nuevo_secuencial=40,
            usuario_id=user_id,
            justificacion="Regularizacion por cierre contable",
        )

    assert updated.secuencial_actual == 40
    assert updated.usuario_auditoria == str(user_id)

    add_calls = session.add.call_args_list
    assert any(call.args and call.args[0] is secuencial for call in add_calls)
    audit_entries = [call.args[0] for call in add_calls if call.args and isinstance(call.args[0], AuditLog)]
    assert len(audit_entries) == 1
    audit = audit_entries[0]
    assert audit.usuario_auditoria == str(user_id)
    assert audit.estado_anterior["secuencial_actual"] == 22
    assert audit.estado_anterior["secuencial_sri"] == "000000022"
    assert audit.estado_nuevo["secuencial_actual"] == 40
    assert audit.estado_nuevo["secuencial_sri"] == "000000040"
    assert audit.estado_nuevo["justificacion"] == "Regularizacion por cierre contable"
    assert audit.estado_nuevo["motivo_salto"] == "Regularizacion por cierre contable"
    assert audit.after_json["delta"] == 18
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(secuencial)


def test_punto_emision_service_ajuste_manual_rechaza_si_no_es_admin():
    session = MagicMock()
    svc = PuntoEmisionService()
    svc.repo = MagicMock()

    usuario = Usuario(
        persona_id=uuid4(),
        rol_id=uuid4(),
        username="operador",
        password_hash="hash",
        requiere_cambio_password=False,
        usuario_auditoria="tester",
        activo=True,
    )
    rol = Rol(nombre="OPERADOR", descripcion="No admin", usuario_auditoria="tester", activo=True)
    first = MagicMock()
    first.first.return_value = (usuario, rol)
    session.exec.side_effect = [first]

    with pytest.raises(HTTPException) as exc:
        svc.ajustar_secuencial_manual(
            session,
            punto_emision_id=uuid4(),
            tipo_documento=TipoDocumentoSRI.FACTURA,
            nuevo_secuencial=10,
            usuario_id=uuid4(),
            justificacion="Ajuste operacional",
        )

    assert exc.value.status_code == 403
    svc.repo.ajustar_secuencial_manual.assert_not_called()


def test_punto_emision_service_ajuste_manual_rechaza_sin_permiso_especifico():
    session = MagicMock()
    svc = PuntoEmisionService()

    user_id = uuid4()
    admin = Usuario(
        id=user_id,
        persona_id=uuid4(),
        rol_id=uuid4(),
        username="admin",
        password_hash="hash",
        requiere_cambio_password=False,
        usuario_auditoria="tester",
        activo=True,
    )
    rol = Rol(id=admin.rol_id, nombre="ADMINISTRADOR", descripcion="Admin", usuario_auditoria="tester", activo=True)
    first = MagicMock()
    first.first.return_value = (admin, rol)
    session.exec.side_effect = [first]

    pe = PuntoEmision(
        id=uuid4(),
        codigo="017",
        descripcion="PE",
        sucursal_id=uuid4(),
        usuario_auditoria="tester",
        activo=True,
    )
    session.get.return_value = pe
    PuntoEmisionSecuencial(
        punto_emision_id=pe.id,
        tipo_documento=TipoDocumentoSRI.FACTURA,
        secuencial_actual=10,
        usuario_auditoria="tester",
        activo=True,
    )

    with patch("osiris.modules.common.punto_emision.service.verificar_permiso", return_value=False):
        with pytest.raises(HTTPException) as exc:
            svc.ajustar_secuencial_manual(
                session,
                punto_emision_id=pe.id,
                tipo_documento=TipoDocumentoSRI.FACTURA,
                nuevo_secuencial=12,
                usuario_id=user_id,
                justificacion="Ajuste no autorizado",
            )
    assert exc.value.status_code == 403
    assert "permiso especifico" in exc.value.detail.lower()


def test_punto_emision_service_ajuste_manual_admin_ok():
    session = MagicMock()
    svc = PuntoEmisionService()

    admin_rol_id = uuid4()
    admin_user_id = uuid4()
    usuario = Usuario(
        id=admin_user_id,
        persona_id=uuid4(),
        rol_id=admin_rol_id,
        username="admin",
        password_hash="hash",
        requiere_cambio_password=False,
        usuario_auditoria="tester",
        activo=True,
    )
    rol = Rol(id=admin_rol_id, nombre="ADMINISTRADOR", descripcion="Admin", usuario_auditoria="tester", activo=True)
    first = MagicMock()
    first.first.return_value = (usuario, rol)
    session.exec.side_effect = [first]

    pe_id = uuid4()
    pe = PuntoEmision(
        id=pe_id,
        codigo="018",
        descripcion="PE 18",
        sucursal_id=uuid4(),
        usuario_auditoria="tester",
        activo=True,
    )
    session.get.return_value = pe
    seq = PuntoEmisionSecuencial(
        punto_emision_id=pe_id,
        tipo_documento=TipoDocumentoSRI.FACTURA,
        secuencial_actual=20,
        usuario_auditoria="tester",
        activo=True,
    )
    second = MagicMock()
    second.one.return_value = seq
    session.exec.side_effect = [first, second]

    with patch("osiris.modules.common.punto_emision.service.verificar_permiso", return_value=True):
        out = svc.ajustar_secuencial_manual(
            session,
            punto_emision_id=pe_id,
            tipo_documento=TipoDocumentoSRI.FACTURA,
            nuevo_secuencial=33,
            usuario_id=admin_user_id,
            justificacion="Ajuste autorizado por cierre fiscal",
        )

    assert out.secuencial_actual == 33
