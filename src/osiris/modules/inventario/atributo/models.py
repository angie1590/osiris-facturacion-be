# src/osiris/modules/inventario/atributo/models.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from osiris.domain.base_models import BaseOSModel
from .entity import TipoDato

class AtributoCreate(BaseOSModel):
    nombre: str
    tipo_dato: TipoDato
    select_options: Optional[list[str]] = None
    catalog_id: Optional[UUID] = None
    allow_negative: bool = False
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    usuario_auditoria: Optional[str] = None

class AtributoUpdate(BaseOSModel):
    nombre: Optional[str] = None
    tipo_dato: Optional[TipoDato] = None
    select_options: Optional[list[str]] = None
    catalog_id: Optional[UUID] = None
    allow_negative: Optional[bool] = None
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    usuario_auditoria: Optional[str] = None

class AtributoRead(BaseOSModel):
    id: UUID
    nombre: str
    tipo_dato: TipoDato
    select_options: Optional[list[str]] = None
    catalog_id: Optional[UUID] = None
    allow_negative: bool = False
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    usuario_auditoria: Optional[str] = None
