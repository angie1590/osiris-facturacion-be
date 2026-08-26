from __future__ import annotations

from typing import Optional
from uuid import UUID
from sqlmodel import Field
from osiris.domain.base_models import BaseTable, AuditMixin, SoftDeleteMixin


class Categoria(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_categoria"

    nombre: str = Field(nullable=False, index=True)

    es_padre: bool = Field(default=False, nullable=False, index=True)

    parent_id: Optional[UUID] = Field(
        foreign_key="tbl_categoria.id",
        nullable=True,
        index=True,
    )
