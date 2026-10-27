from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Mapping
from typing import Any

from fastapi import HTTPException


class CatalogPreviewSigner:
    def __init__(self, secret: bytes, *, ttl_seconds: int = 300) -> None:
        if len(secret) < 32:
            raise ValueError("La clave de preview debe tener al menos 32 bytes.")
        if not 1 <= ttl_seconds <= 3600:
            raise ValueError("La duracion del preview debe estar entre 1 y 3600 segundos.")
        self._secret = secret
        self._ttl_seconds = ttl_seconds

    @staticmethod
    def _encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

    @staticmethod
    def _decode(value: str) -> bytes:
        return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)

    @staticmethod
    def _digest(value: Mapping[str, Any]) -> str:
        canonical = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _signature(self, encoded_claims: str) -> str:
        content = f"osiris.catalog.preview.v1.{encoded_claims}".encode("ascii")
        return self._encode(hmac.new(self._secret, content, hashlib.sha256).digest())

    def issue(
        self,
        *,
        operation: str,
        target: str,
        actor: str,
        payload: Mapping[str, Any],
        state: Mapping[str, Any],
        now: int | None = None,
    ) -> str:
        issued_at = int(time.time()) if now is None else now
        claims = {
            "v": 1,
            "iat": issued_at,
            "exp": issued_at + self._ttl_seconds,
            "binding": self._digest(
                {"operation": operation, "target": target, "actor": actor, "payload": payload}
            ),
            "state": self._digest(state),
        }
        encoded = self._encode(
            json.dumps(claims, sort_keys=True, separators=(",", ":")).encode("ascii")
        )
        return f"{encoded}.{self._signature(encoded)}"

    def verify(
        self,
        token: str,
        *,
        operation: str,
        target: str,
        actor: str,
        payload: Mapping[str, Any],
        state: Mapping[str, Any],
        now: int | None = None,
    ) -> None:
        try:
            if len(token) > 2048:
                raise ValueError("invalid token length")
            encoded, signature = token.split(".")
            if not hmac.compare_digest(signature, self._signature(encoded)):
                raise ValueError("invalid signature")
            claims = json.loads(self._decode(encoded))
            current_time = int(time.time()) if now is None else now
            if (
                not isinstance(claims, dict)
                or claims.get("v") != 1
                or type(claims.get("iat")) is not int
                or type(claims.get("exp")) is not int
                or not claims["iat"] <= current_time < claims["exp"]
                or claims["exp"] - claims["iat"] != self._ttl_seconds
            ):
                raise ValueError("invalid or expired claims")
            binding = self._digest(
                {"operation": operation, "target": target, "actor": actor, "payload": payload}
            )
            if not hmac.compare_digest(claims.get("binding", ""), binding):
                raise ValueError("different operation")
            if not hmac.compare_digest(claims.get("state", ""), self._digest(state)):
                raise ValueError("different state")
        except (ValueError, TypeError, UnicodeError, OverflowError):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "CATALOG_PREVIEW_STALE",
                    "conteos": {},
                    "message": "La previsualizacion cambio, expiro o no corresponde a esta operacion. Genera una nueva previsualizacion.",
                    "acciones_permitidas": ["previsualizar"],
                },
            ) from None
