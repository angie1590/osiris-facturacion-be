# src/osiris/modules/inventario/atributo/models.py
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from osiris.domain.base_models import BaseOSModel
from .entity import TipoDato

class AtributoCreate(BaseOSModel):
    nombre: str
    tipo_dato: TipoDato
    usuario_auditoria: Optional[str] = None

class AtributoUpdate(BaseOSModel):
    nombre: Optional[str] = None
    tipo_dato: Optional[TipoDato] = None
    usuario_auditoria: Optional[str] = None

class AtributoRead(BaseOSModel):
    id: UUID
    nombre: str
    tipo_dato: TipoDato
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    usuario_auditoria: Optional[str] = None
