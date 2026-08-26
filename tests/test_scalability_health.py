from __future__ import annotations

from fastapi.testclient import TestClient

import osiris.main as main_module


def test_health_live_returns_ok():
    with TestClient(main_module.app) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_ready_returns_ok_when_db_is_available(monkeypatch):
    monkeypatch.setattr(main_module, "_check_db_ready_sync", lambda: True)

    with TestClient(main_module.app) as client:
        response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}


def test_health_ready_returns_503_when_db_is_down(monkeypatch):
    def _raise_db_error():
        raise RuntimeError("db down")

    monkeypatch.setattr(main_module, "_check_db_ready_sync", _raise_db_error)

    with TestClient(main_module.app) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "down"}


def test_overload_guard_rejects_when_max_in_flight_limit_reached(monkeypatch):
    monkeypatch.setattr(main_module.app_settings, "SCALABILITY_MAX_IN_FLIGHT_REQUESTS", 1)
    monkeypatch.setattr(main_module, "get_http_in_flight", lambda: 1)

    with TestClient(main_module.app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 503
    assert response.json()["detail"] == "Servidor temporalmente saturado. Reintente en breve."
    assert response.headers.get("X-Request-ID")
