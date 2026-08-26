# src/osiris/modules/inventario/casa_comercial/entity.py
from __future__ import annotations

from sqlmodel import Field
from osiris.domain.base_models import BaseTable, AuditMixin, SoftDeleteMixin

class CasaComercial(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_casa_comercial"

    nombre: str = Field(index=True, nullable=False, unique=True, max_length=120)
