from __future__ import annotations

import base64
import json
import os
from contextvars import ContextVar, Token
from typing import Any, Optional


_current_user_id: ContextVar[Optional[str]] = ContextVar("current_user_id", default=None)
_current_company_id: ContextVar[Optional[str]] = ContextVar("current_company_id", default=None)


def set_current_user_id(user_id: Optional[str]) -> Token:
    return _current_user_id.set(user_id)


def reset_current_user_id(token: Token) -> None:
    _current_user_id.reset(token)


def get_current_user_id() -> Optional[str]:
    return _current_user_id.get()


def set_current_company_id(company_id: Optional[str]) -> Token:
    return _current_company_id.set(company_id)


def reset_current_company_id(token: Token) -> None:
    _current_company_id.reset(token)


def get_current_company_id() -> Optional[str]:
    return _current_company_id.get()


def _allows_x_user_id_header() -> bool:
    """
    X-User-Id se permite solo en entornos no productivos para pruebas
    técnicas/smoke. En producción se exige Authorization.
    """
    environment = os.getenv("ENVIRONMENT", "development").strip().lower()
    return environment in {"development", "dev", "test", "testing", "local", "ci"}


def _decode_jwt_payload(token: str) -> dict[str, Any] | None:
    if "." not in token:
        return None
    try:
        _header, payload_b64, _signature = token.split(".", 2)
        padding = "=" * ((4 - len(payload_b64) % 4) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64 + padding).decode("utf-8")
        payload = json.loads(payload_json)
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def extract_auth_context_from_request_headers(
    *,
    authorization: Optional[str],
    x_user_id: Optional[str],
    x_company_id: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    # Canal principal: Authorization.
    user_id: Optional[str] = None
    company_id: Optional[str] = None

    if authorization:
        token = authorization.strip()
        if token.lower().startswith("bearer "):
            token = token.split(" ", 1)[1].strip()

        # Fallback simple: si el token no es JWT, lo tratamos como ID plano.
        if "." not in token:
            user_id = token or None
        else:
            payload = _decode_jwt_payload(token)
            if payload is None:
                # Si Authorization viene corrupto, no hacemos fallback a headers auxiliares.
                return None, None
            user_id = payload.get("sub") or payload.get("user_id") or payload.get("uid")
            company_id = (
                payload.get("empresa_id")
                or payload.get("company_id")
                or payload.get("tenant_id")
            )
            user_id = str(user_id) if user_id else None
            company_id = str(company_id) if company_id else None

    # Canal auxiliar solo para dev/test/local/ci.
    if _allows_x_user_id_header():
        if user_id is None and x_user_id:
            user_id = x_user_id
        if company_id is None and x_company_id:
            company_id = x_company_id

    return user_id, company_id


def extract_user_id_from_request_headers(*, authorization: Optional[str], x_user_id: Optional[str]) -> Optional[str]:
    user_id, _ = extract_auth_context_from_request_headers(
        authorization=authorization,
        x_user_id=x_user_id,
        x_company_id=None,
    )
    return user_id
