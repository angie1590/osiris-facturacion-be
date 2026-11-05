from __future__ import annotations

from uuid import UUID

from sqlmodel import Field

from osiris.domain.base_models import BaseTable


class ProductoCategoria(BaseTable, table=True):
    __tablename__ = "tbl_producto_categoria"

    producto_id: UUID = Field(foreign_key="tbl_producto.id", index=True, nullable=False)
    categoria_id: UUID = Field(foreign_key="tbl_categoria.id", index=True, nullable=False)