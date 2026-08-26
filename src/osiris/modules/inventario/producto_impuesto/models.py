from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from osiris.domain.base_models import BaseOSModel
from osiris.modules.sri.impuesto_catalogo.models import ImpuestoCatalogoRead


class ProductoImpuestoCreate(BaseOSModel):
    producto_id: UUID
    impuesto_catalogo_id: UUID
    usuario_auditoria: Optional[str] = None


class ProductoImpuestoRead(BaseOSModel):
    id: UUID
    producto_id: UUID
    impuesto_catalogo_id: UUID
    codigo_impuesto_sri: str
    codigo_porcentaje_sri: str
    tarifa: Decimal
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    usuario_auditoria: Optional[str] = None
    impuesto: Optional[ImpuestoCatalogoRead] = None  # Datos completos del impuesto
