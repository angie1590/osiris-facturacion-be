# src/osiris/modules/common/cliente/models.py
from __future__ import annotations

from typing import Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from osiris.domain.base_models import BaseOSModel
from osiris.modules.common.persona.composition import PersonaReference
from osiris.modules.common.persona.models import PersonaRead


class ClienteBase(BaseOSModel):
    persona_id: UUID
    tipo_cliente_id: UUID


class ClienteCreate(PersonaReference):
    model_config = {"extra": "forbid", "from_attributes": True}
    tipo_cliente_id: UUID
    usuario_auditoria: Optional[str] = None


class ClienteUpdate(BaseOSModel):
    model_config = {"extra": "forbid", "from_attributes": True}
    persona_id: Optional[UUID] = None
    tipo_cliente_id: Optional[UUID] = None
    usuario_auditoria: Optional[str] = None


class ClienteRead(BaseOSModel):
    id: UUID
    persona_id: UUID
    tipo_cliente_id: UUID
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    usuario_auditoria: Optional[str] = None
    persona: Optional[PersonaRead] = None
    tipo_cliente_nombre: Optional[str] = None
    descuento: Optional[Decimal] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
