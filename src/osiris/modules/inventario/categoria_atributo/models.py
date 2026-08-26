# src/osiris/modules/inventario/categoria_atributo/models.py
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict

class CategoriaAtributoBase(BaseModel):
    categoria_id: UUID
    atributo_id: UUID
    orden: Optional[int] = None
    obligatorio: Optional[bool] = None
    valor_default: Optional[str] = None
    usuario_auditoria: Optional[str] = None

class CategoriaAtributoCreate(CategoriaAtributoBase):
    pass

class CategoriaAtributoUpdate(BaseModel):
    orden: Optional[int] = None
    obligatorio: Optional[bool] = None
    valor_default: Optional[str] = None
    usuario_auditoria: Optional[str] = None

class AtributoRead(BaseModel):
    id: UUID
    nombre: str
    tipo_dato: str

class CategoriaAtributoRead(CategoriaAtributoBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
