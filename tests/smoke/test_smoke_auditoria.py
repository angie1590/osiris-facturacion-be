from __future__ import annotations

import pytest


pytestmark = pytest.mark.smoke


def test_smoke_audit_logs_listado(client):
    response = client.get("/api/v1/audit-logs", params={"limit": 10, "offset": 0})
    if response.status_code != 200:
        # Compatibilidad con implementaciones que usan el path singular.
        response = client.get("/api/v1/audit-log", params={"limit": 10, "offset": 0})
    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)
