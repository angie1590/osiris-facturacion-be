from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlmodel import Session, select

from osiris.core.db import get_session
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.audit_log.models import AuditLogRead


router = APIRouter(prefix="/api/v1/audit-logs", tags=["Audit Logs"])


@router.get("", response_model=list[AuditLogRead])
def list_audit_logs(
    usuario_id: str | None = Query(default=None),
    fecha_desde: datetime | None = Query(default=None),
    fecha_hasta: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    fecha_expr = func.coalesce(AuditLog.fecha, AuditLog.creado_en)
    stmt = select(AuditLog)

    if usuario_id:
        stmt = stmt.where(
            or_(
                AuditLog.usuario_id == usuario_id,
                AuditLog.updated_by == usuario_id,
                AuditLog.created_by == usuario_id,
                AuditLog.usuario_auditoria == usuario_id,
            )
        )
    if fecha_desde:
        stmt = stmt.where(fecha_expr >= fecha_desde)
    if fecha_hasta:
        stmt = stmt.where(fecha_expr <= fecha_hasta)

    logs = session.exec(stmt.order_by(fecha_expr.desc()).offset(offset).limit(limit)).all()
    return [AuditLogRead.from_entity(log) for log in logs]
