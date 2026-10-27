# src/osiris/modules/inventario/atributo/models.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import field_validator, model_validator

from osiris.domain.base_models import BaseOSModel
from osiris.utils.attribute_code import generate_attribute_code
from .entity import TipoDato

class AtributoCreate(BaseOSModel):
    model_config = {"extra": "forbid"}

    nombre: str
    tipo_dato: TipoDato
    unidad_id: Optional[UUID] = None
    select_options: Optional[list[str]] = None
    catalog_id: Optional[UUID] = None
    allow_negative: bool = False
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    usuario_auditoria: Optional[str] = None

    @field_validator("nombre")
    @classmethod
    def validate_generated_code(cls, value: str) -> str:
        generate_attribute_code(value)
        return value

    @model_validator(mode="after")
    def validate_unit_type(self) -> AtributoCreate:
        if self.unidad_id is not None and self.tipo_dato not in {
            TipoDato.INTEGER, TipoDato.DECIMAL
        }:
            raise ValueError("ATTRIBUTE_UNIT_INVALID_TYPE: la unidad requiere un tipo numerico.")
        return self

class AtributoCreateEnCategoria(AtributoCreate):
    categoria_id: UUID
    orden: Optional[int] = None
    obligatorio: bool = False
    valor_default: Optional[str] = None
    aplicar_default_a_existentes: bool = False
    precondicion_preview: Optional[str] = None

class AtributoUpdate(BaseOSModel):
    model_config = {"extra": "forbid"}

    nombre: Optional[str] = None
    tipo_dato: Optional[TipoDato] = None
    unidad_id: Optional[UUID] = None
    select_options: Optional[list[str]] = None
    catalog_id: Optional[UUID] = None
    allow_negative: Optional[bool] = None
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    usuario_auditoria: Optional[str] = None

    @model_validator(mode="after")
    def validate_unit_type(self) -> AtributoUpdate:
        if (
            self.unidad_id is not None
            and self.tipo_dato is not None
            and self.tipo_dato not in {TipoDato.INTEGER, TipoDato.DECIMAL}
        ):
            raise ValueError("ATTRIBUTE_UNIT_INVALID_TYPE: la unidad requiere un tipo numerico.")
        return self

class AtributoUnidadRead(BaseOSModel):
    id: UUID
    codigo: str
    nombre: str
    simbolo: str
    magnitud_codigo: str


class AtributoRead(BaseOSModel):
    id: UUID
    nombre: str
    codigo: str
    tipo_dato: TipoDato
    unidad_id: Optional[UUID] = None
    unidad: Optional[AtributoUnidadRead] = None
    select_options: Optional[list[str]] = None
    catalog_id: Optional[UUID] = None
    allow_negative: bool = False
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    usuario_auditoria: Optional[str] = None
