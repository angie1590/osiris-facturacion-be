# src/osiris/modules/common/cliente/models.py
from __future__ import annotations

from typing import Optional
from uuid import UUID
from datetime import datetime
from osiris.domain.base_models import BaseOSModel

class ClienteBase(BaseOSModel):
    persona_id: UUID
    tipo_cliente_id: UUID

class ClienteCreate(ClienteBase):
    usuario_auditoria: Optional[str] = None

class ClienteUpdate(BaseOSModel):
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
