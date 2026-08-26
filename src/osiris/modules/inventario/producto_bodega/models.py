# src/osiris/modules/inventario/producto_bodega/models.py
from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import Field

from osiris.domain.base_models import BaseOSModel


class ProductoBodegaCreate(BaseOSModel):
    producto_id: UUID
    bodega_id: UUID
    cantidad: Decimal = Field(default=Decimal("0.0000"), ge=Decimal("0"))
    usuario_auditoria: Optional[str] = None


class ProductoBodegaUpdate(BaseOSModel):
    cantidad: Optional[Decimal] = Field(default=None, ge=Decimal("0"))
    usuario_auditoria: Optional[str] = None


class ProductoBodegaAsignarRequest(BaseOSModel):
    cantidad: Decimal = Field(default=Decimal("0.0000"), ge=Decimal("0"))
    usuario_auditoria: Optional[str] = None


class ProductoBodegaRead(BaseOSModel):
    id: UUID
    producto_id: UUID
    bodega_id: UUID
    cantidad: Decimal
    activo: bool | None = None


class StockDisponibleRead(BaseOSModel):
    producto_id: UUID
    producto_nombre: str
    bodega_id: UUID
    codigo_bodega: str
    nombre_bodega: str
    cantidad_disponible: Decimal
