# src/osiris/modules/inventario/bodega/entity.py
from __future__ import annotations

from typing import Optional
from uuid import UUID
from sqlmodel import Field

from osiris.domain.base_models import BaseTable, AuditMixin, SoftDeleteMixin


class Bodega(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_bodega"

    codigo_bodega: str = Field(index=True, nullable=False, max_length=20)
    nombre_bodega: str = Field(nullable=False, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=255)

    # FK a empresa (obligatorio)
    empresa_id: UUID = Field(
        foreign_key="tbl_empresa.id",
        nullable=False,
        index=True,
    )

    # FK a sucursal (opcional, si la bodega está en una sucursal específica)
    sucursal_id: Optional[UUID] = Field(
        default=None,
        foreign_key="tbl_sucursal.id",
        index=True,
    )
