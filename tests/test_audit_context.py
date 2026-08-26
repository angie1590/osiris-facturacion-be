from __future__ import annotations

import base64
import json

from osiris.core.audit_context import (
    extract_auth_context_from_request_headers,
    extract_user_id_from_request_headers,
)


def _jwt_with_payload(payload: dict) -> str:
    header = {"alg": "none", "typ": "JWT"}
    h = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    p = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{h}.{p}.sig"


def test_extract_user_id_prefers_authorization_over_x_user_id(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    user_id = extract_user_id_from_request_headers(
        authorization="Bearer auth-user-id",
        x_user_id="x-user-id",
    )
    assert user_id == "auth-user-id"


def test_extract_user_id_accepts_x_user_id_only_in_development(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    user_id = extract_user_id_from_request_headers(
        authorization=None,
        x_user_id="x-user-id",
    )
    assert user_id == "x-user-id"


def test_extract_user_id_rejects_x_user_id_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    user_id = extract_user_id_from_request_headers(
        authorization=None,
        x_user_id="x-user-id",
    )
    assert user_id is None


def test_extract_user_id_from_jwt_sub(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    token = _jwt_with_payload({"sub": "jwt-user-id"})
    user_id = extract_user_id_from_request_headers(
        authorization=f"Bearer {token}",
        x_user_id=None,
    )
    assert user_id == "jwt-user-id"


def test_invalid_authorization_does_not_fallback_to_x_user_id(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    user_id = extract_user_id_from_request_headers(
        authorization="Bearer malformed.jwt",
        x_user_id="x-user-id",
    )
    assert user_id is None


def test_extract_auth_context_reads_company_from_jwt(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    token = _jwt_with_payload({"sub": "jwt-user-id", "empresa_id": "company-1"})
    user_id, company_id = extract_auth_context_from_request_headers(
        authorization=f"Bearer {token}",
        x_user_id=None,
        x_company_id=None,
    )
    assert user_id == "jwt-user-id"
    assert company_id == "company-1"


def test_extract_auth_context_accepts_x_company_id_only_in_non_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    user_id, company_id = extract_auth_context_from_request_headers(
        authorization=None,
        x_user_id="x-user-id",
        x_company_id="company-2",
    )
    assert user_id == "x-user-id"
    assert company_id == "company-2"


def test_extract_auth_context_rejects_x_company_id_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    user_id, company_id = extract_auth_context_from_request_headers(
        authorization=None,
        x_user_id=None,
        x_company_id="company-2",
    )
    assert user_id is None
    assert company_id is None
