from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from .entity import AuditLog


class AuditLogRead(BaseModel):
    id: UUID
    tabla_afectada: str
    registro_id: str
    accion: str
    estado_anterior: dict[str, Any]
    estado_nuevo: dict[str, Any]
    usuario_id: str | None = None
    fecha: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_entity(cls, log: AuditLog) -> "AuditLogRead":
        return cls(
            id=log.id,
            tabla_afectada=log.tabla_afectada or log.entidad,
            registro_id=log.registro_id or str(log.entidad_id),
            accion=log.accion,
            estado_anterior=log.estado_anterior,
            estado_nuevo=log.estado_nuevo,
            usuario_id=log.usuario_id or log.updated_by or log.created_by or log.usuario_auditoria,
            fecha=log.fecha or log.creado_en,
        )
