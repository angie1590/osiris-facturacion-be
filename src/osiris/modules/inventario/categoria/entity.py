from __future__ import annotations

from typing import Optional
from uuid import UUID
from sqlalchemy import Index, text
from sqlmodel import Field
from osiris.domain.base_models import BaseTable, AuditMixin, SoftDeleteMixin
from osiris.utils.catalog_index_expressions import normalized_lower_trim


class Categoria(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_categoria"
    __table_args__ = (
        Index(
            "uq_tbl_categoria_root_nombre_historical",
            normalized_lower_trim("nombre"),
            unique=True,
            sqlite_where=text("parent_id IS NULL"),
            postgresql_where=text("parent_id IS NULL"),
        ),
        Index(
            "uq_tbl_categoria_child_nombre_historical",
            "parent_id",
            normalized_lower_trim("nombre"),
            unique=True,
            sqlite_where=text("parent_id IS NOT NULL"),
            postgresql_where=text("parent_id IS NOT NULL"),
        ),
    )

    nombre: str = Field(nullable=False, index=True)

    es_padre: bool = Field(default=False, nullable=False, index=True)
    is_default: bool = Field(
        default=False,
        nullable=False,
        index=True,
        sa_column_kwargs={"server_default": text("false")},
    )

    parent_id: Optional[UUID] = Field(
        foreign_key="tbl_categoria.id",
        nullable=True,
        index=True,
    )
