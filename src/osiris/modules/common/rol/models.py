# src/modules/common/rol/models.py
from datetime import datetime
from typing import Optional
from uuid import UUID
from osiris.domain.base_models import BaseOSModel

# DTOs (Pydantic-only)
class RolCreate(BaseOSModel):
    nombre: str
    descripcion: Optional[str] = None
    usuario_auditoria: Optional[str] = None

class RolUpdate(BaseOSModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    usuario_auditoria: Optional[str] = None

class RolRead(BaseOSModel):
    id: UUID
    nombre: str
    descripcion: Optional[str] = None
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    usuario_auditoria: Optional[str] = None
