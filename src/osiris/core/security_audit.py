from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import Request
from sqlmodel import Session

from osiris.core.permisos import verificar_permiso
from osiris.modules.common.audit_log.entity import AuditLog

PermisoAccion = Literal["leer", "crear", "actualizar", "eliminar"]


@dataclass(frozen=True)
class SensitiveEndpointRule:
    method: str
    path_regex: re.Pattern[str]
    modulo_codigo: str
    accion: PermisoAccion


SENSITIVE_ENDPOINT_RULES: tuple[SensitiveEndpointRule, ...] = (
    SensitiveEndpointRule(
        method="PUT",
        path_regex=re.compile(r"^/api(?:/v1)?/empresas/[0-9a-fA-F-]{36}$"),
        modulo_codigo="EMPRESA",
        accion="actualizar",
    ),
    SensitiveEndpointRule(
        method="POST",
        path_regex=re.compile(
            r"^/api(?:/v1)?/puntos-emision/[0-9a-fA-F-]{36}/secuenciales/[^/]+/ajuste-manual$"
        ),
        modulo_codigo="PUNTOS_EMISION",
        accion="actualizar",
    ),
)


def match_sensitive_rule(method: str, path: str) -> SensitiveEndpointRule | None:
    normalized_method = method.upper()
    for rule in SENSITIVE_ENDPOINT_RULES:
        if rule.method == normalized_method and rule.path_regex.match(path):
            return rule
    return None


def parse_attempted_payload(raw_body: bytes) -> dict[str, Any] | str | None:
    if not raw_body:
        return None
    text = raw_body.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def is_user_authorized_for_rule(
    session: Session,
    *,
    user_id: str,
    rule: SensitiveEndpointRule,
) -> bool:
    try:
        user_uuid = UUID(user_id)
    except (TypeError, ValueError):
        return False
    return verificar_permiso(session, user_uuid, rule.modulo_codigo, rule.accion)


def get_client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def log_unauthorized_access(
    session: Session,
    *,
    request: Request,
    user_id: str | None,
    payload: dict[str, Any] | str | None,
    reason: str,
    rule: SensitiveEndpointRule,
) -> None:
    event_payload = {
        "ip": get_client_ip(request),
        "endpoint": request.url.path,
        "metodo": request.method.upper(),
        "payload_intentado": payload,
        "motivo": reason,
        "modulo": rule.modulo_codigo,
        "accion_requerida": rule.accion,
    }
    audit = AuditLog(
        tabla_afectada="SECURITY",
        registro_id=str(uuid4()),
        entidad="SecurityAccess",
        entidad_id=uuid4(),
        accion="UNAUTHORIZED_ACCESS",
        estado_anterior={},
        estado_nuevo=event_payload,
        before_json={},
        after_json=event_payload,
        usuario_id=user_id,
        usuario_auditoria=user_id,
    )
    session.add(audit)
    session.commit()
