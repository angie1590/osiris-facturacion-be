from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import field_validator
from sqlmodel import Field

from osiris.domain.base_models import BaseOSModel

class ProveedorSociedadBase(BaseOSModel):
    ruc: str = Field(min_length=13, max_length=13)
    razon_social: str
    nombre_comercial: Optional[str] = None
    direccion: str
    telefono: str
    email: str
    tipo_contribuyente_id: str = Field(min_length=2, max_length=2)
    persona_contacto_id: UUID

    @field_validator("ruc")
    @classmethod
    def _ruc_len(cls, v: str) -> str:
        if len(v) != 13:
            raise ValueError("El RUC debe tener 13 dígitos")
        return v


class ProveedorSociedadCreate(ProveedorSociedadBase):
    usuario_auditoria: str


class ProveedorSociedadUpdate(BaseOSModel):
    # Parcial
    ruc: Optional[str] = None
    razon_social: Optional[str] = None
    nombre_comercial: Optional[str] = None
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    tipo_contribuyente_id: Optional[str] = None
    # persona_contacto_id NO se permite cambiar (regla en service)
    usuario_auditoria: Optional[str] = None


class ProveedorSociedadRead(BaseOSModel):
    id: UUID
    ruc: str
    razon_social: str
    nombre_comercial: Optional[str] = None
    direccion: str
    telefono: Optional[str] = None
    email: str
    tipo_contribuyente_id: str
    persona_contacto_id: UUID
    usuario_auditoria: str
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
