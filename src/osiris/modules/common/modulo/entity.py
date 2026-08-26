# src/osiris/modules/common/modulo/entity.py
from __future__ import annotations
from typing import Optional

from sqlmodel import Field
from osiris.domain.base_models import BaseTable, AuditMixin, SoftDeleteMixin


class Modulo(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_modulo"

    codigo: str = Field(
        nullable=False,
        unique=True,
        index=True,
        max_length=50,
        description="Código único del módulo (ej: VENTAS, COMPRAS, INVENTARIO)"
    )
    nombre: str = Field(
        nullable=False,
        max_length=120,
        description="Nombre descriptivo del módulo"
    )
    descripcion: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Texto descriptivo del módulo"
    )
    orden: Optional[int] = Field(
        default=None,
        description="Orden de aparición en menús"
    )
    icono: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Nombre del icono para el frontend"
    )
