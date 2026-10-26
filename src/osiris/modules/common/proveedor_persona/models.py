from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlmodel import Field
from osiris.domain.base_models import BaseOSModel
from osiris.modules.common.persona.composition import PersonaReference
from osiris.modules.common.persona.models import PersonaRead


class ProveedorPersonaCreate(PersonaReference):
    model_config = {"extra": "forbid", "from_attributes": True}
    nombre_comercial: Optional[str] = None
    tipo_contribuyente_id: str = Field(min_length=1, max_length=2)
    usuario_auditoria: Optional[str] = None


class ProveedorPersonaUpdate(BaseOSModel):
    model_config = {"extra": "forbid", "from_attributes": True}
    persona_id: Optional[UUID] = None
    nombre_comercial: Optional[str] = None
    tipo_contribuyente_id: Optional[str] = Field(
        default=None, min_length=1, max_length=2
    )
    usuario_auditoria: Optional[str] = None


class ProveedorPersonaRead(BaseOSModel):
    id: UUID
    nombre_comercial: Optional[str] = None
    tipo_contribuyente_id: str
    persona_id: UUID
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    usuario_auditoria: Optional[str] = None
    persona: Optional[PersonaRead] = None
    tipo_contribuyente_nombre: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
