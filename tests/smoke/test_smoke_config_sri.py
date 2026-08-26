from __future__ import annotations

import pytest

from tests.smoke.flow_helpers import (
    crear_empresa_general,
    crear_punto_emision,
    crear_sucursal,
)


pytestmark = pytest.mark.smoke


def test_smoke_config_sri_basico(client):
    empresa_id = crear_empresa_general(client)
    sucursal_id = crear_sucursal(client, empresa_id)
    punto_emision_id = crear_punto_emision(client, sucursal_id)

    health_response = client.get("http://localhost:8000/health")
    if health_response.status_code != 200:
        health_response = client.get("http://localhost:8000/docs")
    assert health_response.status_code == 200

    puntos_response = client.get("/api/v1/puntos-emision", params={"limit": 20, "offset": 0, "only_active": True})
    assert puntos_response.status_code == 200, puntos_response.text

    secuencial_response = client.post(
        f"/api/v1/puntos-emision/{punto_emision_id}/secuenciales/FACTURA/siguiente",
        json={"usuario_auditoria": "smoke"},
    )
    assert secuencial_response.status_code == 200, secuencial_response.text
    secuencial = secuencial_response.json()["secuencial"]
    assert isinstance(secuencial, str)
    assert len(secuencial) == 9
    assert secuencial.isdigit()
