# src/osiris/modules/inventario/casa_comercial/models.py
from datetime import datetime
from typing import Optional
from uuid import UUID
from osiris.domain.base_models import BaseOSModel

# DTOs (Pydantic-only)
class CasaComercialCreate(BaseOSModel):
    nombre: str
    usuario_auditoria: Optional[str] = None

class CasaComercialUpdate(BaseOSModel):
    nombre: Optional[str] = None
    usuario_auditoria: Optional[str] = None

class CasaComercialRead(BaseOSModel):
    id: UUID
    nombre: str
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    usuario_auditoria: Optional[str] = None
