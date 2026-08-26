from __future__ import annotations

from typing import List, Optional
from uuid import UUID
from sqlmodel import Session, select
from fastapi import HTTPException

from osiris.domain.repository import BaseRepository
from osiris.modules.inventario.producto.entity import ProductoImpuesto
from osiris.modules.sri.impuesto_catalogo.entity import ImpuestoCatalogo, TipoImpuesto


class ProductoImpuestoRepository(BaseRepository):
    model = ProductoImpuesto

    def get_by_producto_impuesto(
        self,
        session: Session,
        producto_id: UUID,
        impuesto_catalogo_id: UUID
    ) -> Optional[ProductoImpuesto]:
        """Obtiene la relación específica producto-impuesto."""
        stmt = select(ProductoImpuesto).where(
            ProductoImpuesto.producto_id == producto_id,
            ProductoImpuesto.impuesto_catalogo_id == impuesto_catalogo_id,
            ProductoImpuesto.activo.is_(True)
        )
        return session.exec(stmt).first()

    def list_by_producto(self, session: Session, producto_id: UUID) -> List[ProductoImpuesto]:
        """Lista todos los impuestos activos asignados a un producto."""
        stmt = select(ProductoImpuesto).where(
            ProductoImpuesto.producto_id == producto_id,
            ProductoImpuesto.activo.is_(True)
        )
        return list(session.exec(stmt).all())

    def count_by_tipo_impuesto(
        self,
        session: Session,
        producto_id: UUID,
        tipo_impuesto: TipoImpuesto
    ) -> int:
        """Cuenta cuántos impuestos de un tipo específico tiene asignado un producto."""
        stmt = select(ProductoImpuesto).join(
            ImpuestoCatalogo,
            ProductoImpuesto.impuesto_catalogo_id == ImpuestoCatalogo.id
        ).where(
            ProductoImpuesto.producto_id == producto_id,
            ProductoImpuesto.activo.is_(True),
            ImpuestoCatalogo.tipo_impuesto == tipo_impuesto,
            ImpuestoCatalogo.activo.is_(True)
        )

        resultados = session.exec(stmt).all()
        return len(resultados)

    def validar_duplicado(
        self,
        session: Session,
        producto_id: UUID,
        impuesto_catalogo_id: UUID
    ) -> None:
        """Valida que no exista ya una asignación activa de este impuesto al producto."""
        existente = self.get_by_producto_impuesto(session, producto_id, impuesto_catalogo_id)
        if existente:
            raise HTTPException(
                status_code=409,
                detail="Este impuesto ya está asignado al producto"
            )

    def validar_maximo_por_tipo(
        self,
        session: Session,
        producto_id: UUID,
        tipo_impuesto: TipoImpuesto
    ) -> None:
        """Valida que no se exceda el máximo de un impuesto por tipo (IVA o ICE)."""
        count = self.count_by_tipo_impuesto(session, producto_id, tipo_impuesto)
        if count >= 1:
            raise HTTPException(
                status_code=400,
                detail=f"El producto ya tiene un impuesto de tipo {tipo_impuesto.value} asignado. Máximo permitido: 1"
            )

    def delete_by_id(self, session: Session, producto_impuesto_id: UUID) -> bool:
        """Elimina (soft delete) una asignación de impuesto."""
        producto_impuesto = self.get(session, producto_impuesto_id)
        if not producto_impuesto:
            raise HTTPException(status_code=404, detail="Asignación de impuesto no encontrada")

        return self.delete(session, producto_impuesto)
