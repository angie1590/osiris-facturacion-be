from osiris.modules.common.auth_router import ApprovalCodeRequest
from osiris.core.auth import verify_approval_code
from osiris.core.security import hash_password
from types import SimpleNamespace


def test_approval_code_requires_four_digits():
    assert ApprovalCodeRequest(approval_code="2015").approval_code == "2015"


def test_approval_code_rejects_non_numeric_value():
    try:
        ApprovalCodeRequest(approval_code="20A5")
    except ValueError:
        return
    raise AssertionError("Se esperaba rechazo de PIN no numerico")


def test_approval_code_verifies_against_hash():
    usuario = SimpleNamespace(codigo_aprobacion_hash=hash_password("2015"))
    assert verify_approval_code(usuario, "2015")
    assert not verify_approval_code(usuario, "9999")
