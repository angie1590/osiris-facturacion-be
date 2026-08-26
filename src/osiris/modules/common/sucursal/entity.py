from __future__ import annotations
from decimal import Decimal
from typing import Optional
from uuid import UUID
from sqlalchemy import CheckConstraint, Column, UniqueConstraint
from sqlalchemy.types import Numeric
from sqlmodel import Field

from osiris.domain.base_models import BaseTable, AuditMixin, SoftDeleteMixin


class Sucursal(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_sucursal"
    __table_args__ = (
        UniqueConstraint("empresa_id", "codigo", name="uq_sucursal_empresa_codigo"),
        CheckConstraint(
            "(codigo = '001' AND es_matriz = true) OR (codigo != '001' AND es_matriz = false)",
            name="ck_sucursal_matriz_codigo",
        ),
        CheckConstraint(
            "(latitud IS NULL OR (latitud >= -90 AND latitud <= 90))",
            name="ck_sucursal_latitud_rango",
        ),
        CheckConstraint(
            "(longitud IS NULL OR (longitud >= -180 AND longitud <= 180))",
            name="ck_sucursal_longitud_rango",
        ),
    )

    codigo: str = Field(index=True, nullable=False, max_length=3)
    nombre: str = Field(nullable=False, max_length=50)
    direccion: str = Field(nullable=False, max_length=100)
    telefono: Optional[str] = Field(default=None, max_length=15)
    latitud: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(9, 6), nullable=True))
    longitud: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(9, 6), nullable=True))
    es_matriz: bool = Field(default=False, nullable=False)

    # FK a empresa (forma simple y consistente)
    empresa_id: UUID = Field(
        foreign_key="tbl_empresa.id",
        nullable=False,
    )
