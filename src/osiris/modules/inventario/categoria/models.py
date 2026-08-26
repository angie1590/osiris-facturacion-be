from __future__ import annotations

from typing import Optional
from uuid import UUID
from datetime import datetime
from osiris.domain.base_models import BaseOSModel


class CategoriaBase(BaseOSModel):
    nombre: str
    es_padre: bool
    parent_id: Optional[UUID] = None


class CategoriaCreate(CategoriaBase):
    usuario_auditoria: Optional[str] = None


class CategoriaUpdate(BaseOSModel):
    nombre: Optional[str] = None
    es_padre: Optional[bool] = None
    parent_id: Optional[UUID] = None
    usuario_auditoria: Optional[str] = None


class CategoriaRead(BaseOSModel):
    id: UUID
    nombre: str
    es_padre: bool
    parent_id: Optional[UUID] = None
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    usuario_auditoria: Optional[str] = None
