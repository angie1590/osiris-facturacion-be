# src/osiris/modules/inventario/bodega/service.py
from __future__ import annotations

from typing import Optional
from uuid import UUID
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlmodel import select
from sqlalchemy import func
from fastapi import HTTPException

from osiris.core.company_scope import resolve_company_scope
from osiris.modules.inventario.bodega.entity import Bodega
from osiris.modules.inventario.movimientos.models import InventarioStock
from osiris.modules.inventario.producto.entity import ProductoBodega
from .models import BodegaCreate, BodegaUpdate


class BodegaService:
    def list_paginated(
        self,
        session: Session,
        skip: int = 0,
        limit: int = 50,
        empresa_id: Optional[UUID] = None,
        sucursal_id: Optional[UUID] = None,
    ) -> list[Bodega]:
        empresa_scope = resolve_company_scope(requested_company_id=empresa_id)
        query = select(Bodega).where(Bodega.activo.is_(True))
        if empresa_scope:
            query = query.where(Bodega.empresa_id == empresa_scope)
        if sucursal_id:
            query = query.where(Bodega.sucursal_id == sucursal_id)
        query = query.offset(skip).limit(limit)
        return list(session.exec(query))

    def get(self, session: Session, id: UUID) -> Optional[Bodega]:
        entity = session.get(Bodega, id)
        if entity is None:
            return None
        empresa_scope = resolve_company_scope()
        if empresa_scope is not None and entity.empresa_id != empresa_scope:
            raise HTTPException(status_code=403, detail="No autorizado para acceder a bodegas de otra empresa.")
        return entity

    def create(
        self,
        session: Session,
        dto: BodegaCreate,
        usuario_auditoria: Optional[str] = None,
    ) -> Bodega:
        empresa_scope = resolve_company_scope(requested_company_id=dto.empresa_id)
        entity = Bodega(
            codigo_bodega=dto.codigo_bodega,
            nombre_bodega=dto.nombre_bodega,
            descripcion=dto.descripcion,
            empresa_id=empresa_scope or dto.empresa_id,
            sucursal_id=dto.sucursal_id,
            usuario_auditoria=usuario_auditoria or "api",
            activo=True,
        )
        session.add(entity)
        session.commit()
        session.refresh(entity)
        return entity

    def update(
        self,
        session: Session,
        id: UUID,
        dto: BodegaUpdate,
        usuario_auditoria: Optional[str] = None,
    ) -> Optional[Bodega]:
        entity = session.get(Bodega, id)
        if not entity:
            return None
        empresa_scope = resolve_company_scope()
        if empresa_scope is not None and entity.empresa_id != empresa_scope:
            raise HTTPException(status_code=403, detail="No autorizado para modificar bodegas de otra empresa.")
        if dto.codigo_bodega is not None:
            entity.codigo_bodega = dto.codigo_bodega
        if dto.nombre_bodega is not None:
            entity.nombre_bodega = dto.nombre_bodega
        if dto.descripcion is not None:
            entity.descripcion = dto.descripcion
        if dto.sucursal_id is not None:
            entity.sucursal_id = dto.sucursal_id
        entity.usuario_auditoria = usuario_auditoria or entity.usuario_auditoria
        session.add(entity)
        session.commit()
        session.refresh(entity)
        return entity

    def delete(
        self,
        session: Session,
        id: UUID,
        usuario_auditoria: Optional[str] = None,
    ) -> bool:
        entity = session.get(Bodega, id)
        if not entity:
            return False
        empresa_scope = resolve_company_scope()
        if empresa_scope is not None and entity.empresa_id != empresa_scope:
            raise HTTPException(status_code=403, detail="No autorizado para eliminar bodegas de otra empresa.")

        # Regla: una bodega no se puede eliminar lógicamente si mantiene productos asignados
        # o stock materializado con saldo mayor a cero.
        relacion_activa = session.exec(
            select(ProductoBodega.id).where(
                ProductoBodega.bodega_id == id,
                ProductoBodega.activo.is_(True),
            )
        ).first()
        if relacion_activa is not None:
            raise HTTPException(
                status_code=400,
                detail="No se puede eliminar la bodega porque tiene productos asignados.",
            )

        saldo = session.exec(
            select(func.coalesce(func.sum(InventarioStock.cantidad_actual), 0)).where(
                InventarioStock.bodega_id == id,
                InventarioStock.activo.is_(True),
            )
        ).one()
        if Decimal(str(saldo or 0)) > Decimal("0"):
            raise HTTPException(
                status_code=400,
                detail="No se puede eliminar la bodega porque tiene stock disponible.",
            )

        entity.activo = False
        entity.usuario_auditoria = usuario_auditoria or entity.usuario_auditoria
        session.add(entity)
        session.commit()
        return True
