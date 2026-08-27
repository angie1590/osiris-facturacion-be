from osiris.modules.common.auth_router import ApprovalCodeRequest


def test_approval_code_requires_four_digits():
    assert ApprovalCodeRequest(approval_code="2015").approval_code == "2015"


def test_approval_code_rejects_non_numeric_value():
    try:
        ApprovalCodeRequest(approval_code="20A5")
    except ValueError:
        return
    raise AssertionError("Se esperaba rechazo de PIN no numerico")
