# src/osiris/modules/inventario/atributo/entity.py
from __future__ import annotations

from enum import Enum
from decimal import Decimal
from uuid import UUID

from sqlalchemy import JSON, Column, Numeric
from sqlmodel import Field

from osiris.domain.base_models import BaseTable, AuditMixin, SoftDeleteMixin
from osiris.modules.common.catalogo.entity import Catalogo  # noqa: F401

class TipoDato(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    SELECT = "select"
    CATALOG = "catalog"

class Atributo(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_atributo"

    nombre: str = Field(index=True, nullable=False, max_length=120)
    tipo_dato: TipoDato = Field(nullable=False)
    select_options: list[str] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    catalog_id: UUID | None = Field(default=None, foreign_key="tbl_catalogo.id", index=True)
    allow_negative: bool = Field(default=False, nullable=False)
    min_value: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 6), nullable=True))
    max_value: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 6), nullable=True))
