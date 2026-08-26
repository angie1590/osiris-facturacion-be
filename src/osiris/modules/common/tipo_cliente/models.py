from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import Field
from osiris.domain.base_models import BaseOSModel


class TipoClienteBase(BaseOSModel):
    nombre: str
    descuento: Decimal = Field(ge=0, le=100)


class TipoClienteCreate(TipoClienteBase):
    usuario_auditoria: str
    pass


class TipoClienteUpdate(BaseOSModel):
    nombre: Optional[str] = None
    descuento: Optional[Decimal] = Field(default=None, ge=0, le=100)
    usuario_auditoria: Optional[str] = None


class TipoClienteRead(TipoClienteBase):
    id: UUID
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    usuario_auditoria: str
