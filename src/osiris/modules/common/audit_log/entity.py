from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Column, event
from sqlmodel import Field

from osiris.domain.base_models import BaseTable


class AuditAction(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    ANULAR = "ANULAR"


class AuditLog(BaseTable, table=True):
    __tablename__ = "audit_log"

    # Campos canonicos solicitados por E2-2.
    tabla_afectada: str | None = Field(default=None, max_length=100, index=True)
    registro_id: str | None = Field(default=None, max_length=120, index=True)
    entidad: str = Field(nullable=False, max_length=100, index=True)
    entidad_id: UUID = Field(nullable=False, index=True)
    accion: str = Field(nullable=False, max_length=20, default="UPDATE")
    estado_anterior: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    estado_nuevo: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    before_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    after_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_by: str | None = Field(default=None, max_length=255, index=True)
    updated_by: str | None = Field(default=None, max_length=255, index=True)
    usuario_id: str | None = Field(default=None, max_length=255, index=True)
    usuario_auditoria: str | None = Field(default=None, max_length=255)
    fecha: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)
    creado_en: datetime = Field(default_factory=datetime.utcnow, nullable=False)


@event.listens_for(AuditLog, "before_insert")
def _sync_auditlog_legacy_and_standard(_mapper, _connection, target: AuditLog):
    target.tabla_afectada = target.tabla_afectada or target.entidad
    target.registro_id = target.registro_id or str(target.entidad_id)
    target.usuario_id = (
        target.usuario_id
        or target.updated_by
        or target.created_by
        or target.usuario_auditoria
    )
    target.fecha = target.fecha or target.creado_en or datetime.utcnow()
    target.before_json = target.before_json if target.before_json is not None else target.estado_anterior
    target.after_json = target.after_json if target.after_json is not None else target.estado_nuevo
    target.created_by = target.created_by or target.usuario_id
    target.updated_by = target.updated_by or target.usuario_id
