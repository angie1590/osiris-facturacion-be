from __future__ import annotations
from decimal import Decimal
from typing import Annotated, Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, ConfigDict, StringConstraints

Nombre = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=50)]
Direccion = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=100)]
Telefono = Annotated[str, StringConstraints(pattern=r"^\d{7,10}$")]
UsuarioAuditoria = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=50)]

Codigo3 = Annotated[str, StringConstraints(min_length=3, max_length=3)]


class SucursalBase(BaseModel):
    codigo: Codigo3
    nombre: str
    direccion: str
    telefono: Optional[Telefono] = None
    latitud: Optional[Decimal] = None
    longitud: Optional[Decimal] = None
    es_matriz: bool = False
    usuario_auditoria: str
    empresa_id: UUID

class SucursalCreate(SucursalBase):
    """POST/PUT (reemplazo total)."""
    pass

class SucursalUpdate(BaseModel):
    nombre: Optional[Nombre] = None
    direccion: Optional[Direccion] = None
    telefono: Optional[Telefono] = None
    latitud: Optional[Decimal] = None
    longitud: Optional[Decimal] = None
    es_matriz: Optional[bool] = None
    activo: Optional[bool] = True
    usuario_auditoria: Optional[UsuarioAuditoria] = None

class SucursalRead(SucursalBase):
    id: UUID
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    usuario_auditoria: str

    model_config = ConfigDict(from_attributes=True)
