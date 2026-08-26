# src/osiris/modules/common/modulo/models.py
from datetime import datetime
from typing import Optional
from uuid import UUID
from osiris.domain.base_models import BaseOSModel


class ModuloCreate(BaseOSModel):
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    orden: Optional[int] = None
    icono: Optional[str] = None
    usuario_auditoria: Optional[str] = None


class ModuloUpdate(BaseOSModel):
    codigo: Optional[str] = None
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    orden: Optional[int] = None
    icono: Optional[str] = None
    usuario_auditoria: Optional[str] = None


class ModuloRead(BaseOSModel):
    id: UUID
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    orden: Optional[int] = None
    icono: Optional[str] = None
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    usuario_auditoria: Optional[str] = None
