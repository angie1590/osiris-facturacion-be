from __future__ import annotations

from datetime import datetime
from datetime import date
from decimal import Decimal
from typing import Any, ClassVar, Optional
from uuid import UUID

from sqlalchemy import JSON, Boolean, CheckConstraint, Date, Integer, String, UniqueConstraint
from sqlmodel import Column, Field, Numeric
from sqlmodel._compat import SQLModelConfig

from osiris.domain.base_models import AuditMixin, BaseOSModel, BaseTable, SoftDeleteMixin


class ProductoAtributoValor(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_producto_atributo_valor"
    __table_args__ = (
        UniqueConstraint("producto_id", "atributo_id", name="uq_producto_atributo"),
        CheckConstraint(
            """
            (
                CASE WHEN valor_string IS NOT NULL THEN 1 ELSE 0 END +
                CASE WHEN valor_integer IS NOT NULL THEN 1 ELSE 0 END +
                CASE WHEN valor_decimal IS NOT NULL THEN 1 ELSE 0 END +
                CASE WHEN valor_boolean IS NOT NULL THEN 1 ELSE 0 END +
                CASE WHEN valor_date IS NOT NULL THEN 1 ELSE 0 END
            ) = 1
            """,
            name="ck_producto_atributo_valor_one_nonnull",
        ),
    )

    producto_id: UUID = Field(foreign_key="tbl_producto.id", index=True, nullable=False)
    atributo_id: UUID = Field(foreign_key="tbl_atributo.id", index=True, nullable=False)

    valor_string: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    valor_integer: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    valor_decimal: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(18, 6), nullable=True),
    )
    valor_boolean: bool | None = Field(default=None, sa_column=Column(Boolean, nullable=True))
    valor_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True))


class ProductoAtributoRemapeo(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_producto_atributo_remapeo"

    producto_id: UUID = Field(foreign_key="tbl_producto.id", index=True, nullable=False)
    atributo_id: UUID = Field(foreign_key="tbl_atributo.id", index=True, nullable=False)
    tipo_anterior: str = Field(nullable=False, max_length=20)
    tipo_nuevo: str = Field(nullable=False, max_length=20)
    valor_anterior: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    motivo: str = Field(nullable=False, max_length=255)


class ProductoAtributoValorUpsert(BaseOSModel):
    atributo_id: UUID
    valor: Any


class ProductoAtributoRemapeoResolve(BaseOSModel):
    id: UUID
    valor: Any


class ProductoAtributoValorRead(BaseOSModel):
    model_config: ClassVar[SQLModelConfig] = {"from_attributes": True}

    id: UUID
    producto_id: UUID
    atributo_id: UUID
    valor_string: Optional[str] = None
    valor_integer: Optional[int] = None
    valor_decimal: Optional[Decimal] = None
    valor_boolean: Optional[bool] = None
    valor_date: Optional[date] = None
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    usuario_auditoria: Optional[str] = None
