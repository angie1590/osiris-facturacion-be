# src/osiris/modules/inventario/atributo/entity.py
from __future__ import annotations

from datetime import datetime
from enum import Enum
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, Column, Index, Numeric, event, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapper
from sqlmodel import Field

from osiris.domain.base_models import BaseTable, AuditMixin, SoftDeleteMixin
from osiris.modules.common.catalogo.entity import Catalogo  # noqa: F401
from osiris.modules.common.unidad.entity import Unidad  # noqa: F401
from osiris.utils.attribute_code import generate_attribute_code
from osiris.utils.catalog_index_expressions import normalized_lower_trim


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
    __table_args__ = (
        Index(
            "uq_tbl_atributo_codigo_normalizado",
            normalized_lower_trim("codigo"),
            unique=True,
        ),
        Index(
            "uq_tbl_atributo_nombre_activo_normalized",
            normalized_lower_trim("nombre"),
            unique=True,
            postgresql_where=text("activo IS TRUE"),
            sqlite_where=text("activo = 1"),
        ),
        CheckConstraint(
            "unidad_id IS NULL OR lower(CAST(tipo_dato AS VARCHAR)) IN ('integer', 'decimal')",
            name="ck_tbl_atributo_unidad_tipo_numerico",
        ),
        CheckConstraint(
            "length(codigo) BETWEEN 1 AND 120 AND codigo ~ '^[a-z][a-z0-9]*(_[a-z0-9]+)*$'",
            name="ck_tbl_atributo_codigo_normalized",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint(
            "length(codigo) BETWEEN 1 AND 120 AND codigo NOT GLOB '*[^a-z0-9_]*' "
            "AND substr(codigo, 1, 1) GLOB '[a-z]' AND substr(codigo, -1) != '_' "
            "AND instr(codigo, '__') = 0",
            name="ck_tbl_atributo_codigo_normalized",
        ).ddl_if(dialect="sqlite"),
    )

    nombre: str = Field(nullable=False, max_length=120)
    codigo: str = Field(default=None, nullable=False, max_length=120)
    unidad_id: UUID | None = Field(
        default=None, foreign_key="tbl_unidad.id", index=True
    )
    tipo_dato: TipoDato = Field(nullable=False)
    select_options: list[str] | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    catalog_id: UUID | None = Field(
        default=None, foreign_key="tbl_catalogo.id", index=True
    )
    allow_negative: bool = Field(
        default=False, nullable=False, sa_column_kwargs={"server_default": text("false")}
    )
    min_value: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(18, 6), nullable=True)
    )
    max_value: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(18, 6), nullable=True)
    )


@event.listens_for(Atributo, "before_insert")
def _generate_attribute_code(
    _mapper: Mapper[Any], _connection: Connection, target: Atributo
) -> None:
    if target.codigo is None:
        target.codigo = generate_attribute_code(target.nombre)


class AtributoCambio(BaseTable, AuditMixin, table=True):
    __tablename__ = "tbl_atributo_cambio"

    atributo_id: UUID = Field(foreign_key="tbl_atributo.id", index=True, nullable=False)
    operacion: str = Field(nullable=False, max_length=20)
    definicion_anterior: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    definicion_posterior: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    asignaciones_anteriores: list[dict[str, Any]] = Field(
        sa_column=Column(JSON, nullable=False)
    )
    asignaciones_posteriores: list[dict[str, Any]] = Field(
        sa_column=Column(JSON, nullable=False)
    )
    valores_anteriores: list[dict[str, Any]] = Field(
        sa_column=Column(JSON, nullable=False)
    )
    valores_posteriores: list[dict[str, Any]] = Field(
        sa_column=Column(JSON, nullable=False)
    )
    remapeos_anteriores: list[dict[str, Any]] = Field(
        sa_column=Column(JSON, nullable=False)
    )
    remapeos_posteriores: list[dict[str, Any]] = Field(
        sa_column=Column(JSON, nullable=False)
    )
    revertido: bool = Field(default=False, nullable=False, index=True)
    revertido_en: datetime | None = Field(default=None, nullable=True)
