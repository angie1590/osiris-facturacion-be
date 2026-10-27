from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock

from osiris.core.auth import require_roles
from osiris.modules.common.rol.entity import Rol


def _guarded_user(role_name: str):
    user = SimpleNamespace(rol_id=uuid4())
    session = MagicMock()
    session.get.return_value = Rol(nombre=role_name, activo=True, usuario_auditoria="test")
    return user, session


def test_category_and_attribute_mutations_allow_admin_and_supervisor_only():
    admin_guard = require_roles("admin", "supervisor")
    admin, session = _guarded_user("administrador")
    assert admin_guard(usuario=admin, session=session) is admin

    supervisor, supervisor_session = _guarded_user("supervisor")
    assert admin_guard(usuario=supervisor, session=supervisor_session) is supervisor

    operator, operator_session = _guarded_user("operador")
    with pytest.raises(HTTPException) as exc_info:
        admin_guard(usuario=operator, session=operator_session)
    assert exc_info.value.status_code == 403


def test_product_mutations_allow_operator_role():
    product_guard = require_roles("admin", "operator", "supervisor")
    operator, session = _guarded_user("operador")

    assert product_guard(usuario=operator, session=session) is operator


def test_admin_bypasses_role_specific_guards():
    admin, session = _guarded_user("  ADMINISTRADOR  ")
    assert require_roles("operator")(usuario=admin, session=session) is admin


def test_inactive_admin_does_not_bypass_role_guards():
    admin, session = _guarded_user("admin")
    session.get.return_value.activo = False

    with pytest.raises(HTTPException) as exc_info:
        require_roles("operator")(usuario=admin, session=session)

    assert exc_info.value.status_code == 403
