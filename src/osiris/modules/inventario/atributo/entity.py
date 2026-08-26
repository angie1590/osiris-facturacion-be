# src/osiris/modules/inventario/atributo/entity.py
from __future__ import annotations

from enum import Enum
from sqlmodel import Field
from osiris.domain.base_models import BaseTable, AuditMixin, SoftDeleteMixin

class TipoDato(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"

class Atributo(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_atributo"

    nombre: str = Field(index=True, nullable=False, unique=True, max_length=120)
    tipo_dato: TipoDato = Field(nullable=False)
