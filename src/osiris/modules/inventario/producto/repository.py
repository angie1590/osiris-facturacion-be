from typing import Iterable
from uuid import UUID

from sqlalchemy import delete
from sqlmodel import Session, col
from osiris.domain.repository import BaseRepository
from .entity import (
    Producto,
    ProductoProveedorPersona,
    ProductoProveedorSociedad,
)


class ProductoRepository(BaseRepository):
    model = Producto

    def set_proveedores_persona(
        self, session: Session, producto_id: UUID, prov_ids: Iterable[UUID]
    ) -> None:
        session.execute(
            delete(ProductoProveedorPersona).where(
                col(ProductoProveedorPersona.producto_id) == producto_id
            )
        )
        for pid in prov_ids:
            session.add(
                ProductoProveedorPersona(
                    producto_id=producto_id, proveedor_persona_id=pid
                )
            )
        session.flush()

    def set_proveedores_sociedad(
        self, session: Session, producto_id: UUID, prov_ids: Iterable[UUID]
    ) -> None:
        session.execute(
            delete(ProductoProveedorSociedad).where(
                col(ProductoProveedorSociedad.producto_id) == producto_id
            )
        )
        for sid in prov_ids:
            session.add(
                ProductoProveedorSociedad(
                    producto_id=producto_id, proveedor_sociedad_id=sid
                )
            )
        session.flush()
