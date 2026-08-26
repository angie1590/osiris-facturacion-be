# src/osiris/modules/common/rol/entity.py
from __future__ import annotations
from typing import Optional

from sqlmodel import Field
from osiris.domain.base_models import BaseTable, AuditMixin, SoftDeleteMixin

class Rol(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_rol"

    # mismos campos y restricciones que ya tienes
    nombre: str = Field(index=True, nullable=False, unique=True, max_length=120)
    descripcion: Optional[str] = Field(default=None, max_length=255)
