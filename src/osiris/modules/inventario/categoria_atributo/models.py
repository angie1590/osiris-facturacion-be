# src/osiris/modules/inventario/categoria_atributo/models.py
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID
from typing import Literal
from pydantic import BaseModel, ConfigDict


class CategoriaAtributoBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    categoria_id: UUID
    atributo_id: UUID
    orden: Optional[int] = None
    obligatorio: Optional[bool] = None
    valor_default: Optional[str] = None
    aplicar_default_a_existentes: bool = False
    usuario_auditoria: Optional[str] = None


class CategoriaAtributoCreate(CategoriaAtributoBase):
    model_config = ConfigDict(extra="forbid")


class CategoriaAtributoUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    orden: Optional[int] = None
    obligatorio: Optional[bool] = None
    valor_default: Optional[str] = None
    aplicar_default_a_existentes: bool = False
    precondicion_preview: Optional[str] = None
    usuario_auditoria: Optional[str] = None


class CategoriaAtributoRemoveConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmar: Literal[True]
    precondicion_preview: str


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
