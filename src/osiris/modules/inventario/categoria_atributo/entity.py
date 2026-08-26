# src/osiris/modules/inventario/categoria_atributo/entity.py
from __future__ import annotations

from uuid import UUID
from sqlmodel import Field
from osiris.domain.base_models import BaseTable, AuditMixin, SoftDeleteMixin


class CategoriaAtributo(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_categoria_atributo"

    categoria_id: UUID = Field(foreign_key="tbl_categoria.id", index=True, nullable=False)
    atributo_id: UUID = Field(foreign_key="tbl_atributo.id", index=True, nullable=False)
    orden: int | None = Field(default=None)
    obligatorio: bool | None = Field(default=None)
    valor_default: str | None = Field(default=None, nullable=True)
