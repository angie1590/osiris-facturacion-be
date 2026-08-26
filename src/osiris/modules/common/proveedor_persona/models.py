from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlmodel import SQLModel, Field
from pydantic import ConfigDict


class ProveedorPersonaCreate(SQLModel):
    nombre_comercial: Optional[str] = None
    tipo_contribuyente_id: str = Field(min_length=1, max_length=2)
    persona_id: UUID
    usuario_auditoria: Optional[str] = None


class ProveedorPersonaUpdate(SQLModel):
    # No se permite cambiar persona_id (igual que cliente)
    nombre_comercial: Optional[str] = None
    tipo_contribuyente_id: Optional[str] = Field(default=None, min_length=1, max_length=2)
    usuario_auditoria: Optional[str] = None


class ProveedorPersonaRead(SQLModel):
    id: UUID
    nombre_comercial: Optional[str] = None
    tipo_contribuyente_id: str
    persona_id: UUID
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    usuario_auditoria: str

    model_config = ConfigDict(from_attributes=True)
