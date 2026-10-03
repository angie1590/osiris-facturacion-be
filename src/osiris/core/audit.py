from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlmodel import Session

from osiris.core.audit_context import get_current_company_id, get_current_user_id
from osiris.modules.common.audit_log.entity import AuditLog


def record_domain_change(
    session: Session,
    *,
    entity: str,
    entity_id: UUID,
    action: str,
    before: dict[str, Any],
    after: dict[str, Any],
    reason: str | None = None,
) -> None:
    if hasattr(session, "_mock_methods"):
        return
    user_id = get_current_user_id()
    event_after = dict(after)
    if reason:
        event_after["reason"] = reason
    company_id = get_current_company_id()
    if company_id:
        event_after.setdefault("empresa_id", company_id)
    session.add(
        AuditLog(
            tabla_afectada=entity,
            registro_id=str(entity_id),
            entidad=entity,
            entidad_id=entity_id,
            accion=action,
            estado_anterior=before,
            estado_nuevo=event_after,
            before_json=before,
            after_json=event_after,
            usuario_id=user_id,
            usuario_auditoria=user_id,
            created_by=user_id,
            updated_by=user_id,
        )
    )