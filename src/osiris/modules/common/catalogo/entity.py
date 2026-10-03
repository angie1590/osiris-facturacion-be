from __future__ import annotations

from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlmodel import Field

from osiris.domain.base_models import AuditMixin, BaseTable, SoftDeleteMixin


class Catalogo(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_catalogo"
    __table_args__ = (UniqueConstraint("nombre", name="uq_tbl_catalogo_nombre"),)

    nombre: str = Field(nullable=False, max_length=120, index=True)
    descripcion: str | None = Field(default=None, max_length=500)


class CatalogoValor(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_catalogo_valor"

    catalogo_id: UUID = Field(foreign_key="tbl_catalogo.id", nullable=False, index=True)
    valor: str = Field(nullable=False, max_length=255)
    orden: int = Field(default=0, nullable=False)