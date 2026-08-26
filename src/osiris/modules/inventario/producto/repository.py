from typing import Iterable
from uuid import UUID

from sqlalchemy import delete
from sqlmodel import Session
from osiris.domain.repository import BaseRepository
from .entity import (
    Producto,
    ProductoCategoria,
    ProductoProveedorPersona,
    ProductoProveedorSociedad,
)

class ProductoRepository(BaseRepository):
    model = Producto

    def set_categorias(self, session: Session, producto_id: UUID, categoria_ids: Iterable[UUID]) -> None:
        session.exec(
            delete(ProductoCategoria).where(ProductoCategoria.producto_id == producto_id)
        )
        for cid in categoria_ids:
            session.add(ProductoCategoria(producto_id=producto_id, categoria_id=cid))
        session.flush()

    def set_proveedores_persona(self, session: Session, producto_id: UUID, prov_ids: Iterable[UUID]) -> None:
        session.exec(
            delete(ProductoProveedorPersona).where(ProductoProveedorPersona.producto_id == producto_id)
        )
        for pid in prov_ids:
            session.add(ProductoProveedorPersona(producto_id=producto_id, proveedor_persona_id=pid))
        session.flush()

    def set_proveedores_sociedad(self, session: Session, producto_id: UUID, prov_ids: Iterable[UUID]) -> None:
        session.exec(
            delete(ProductoProveedorSociedad).where(ProductoProveedorSociedad.producto_id == producto_id)
        )
        for sid in prov_ids:
            session.add(ProductoProveedorSociedad(producto_id=producto_id, proveedor_sociedad_id=sid))
        session.flush()
