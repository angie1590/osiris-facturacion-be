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
    confirmar_limpieza_colision: bool = False
    usuario_auditoria: Optional[str] = None


class CategoriaRead(BaseOSModel):
    id: UUID
    nombre: str
    es_padre: bool
    is_default: bool = False
    parent_id: Optional[UUID] = None
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    usuario_auditoria: Optional[str] = None


class RecategorizarProducto(BaseOSModel):
    producto_id: UUID
    categoria_id: UUID


class RecategorizarProductosRequest(BaseOSModel):
    assignments: list[RecategorizarProducto]
