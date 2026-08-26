# src/osiris/modules/common/usuario/models.py
from __future__ import annotations
from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import Field as PydField
from osiris.domain.base_models import BaseOSModel

class UsuarioBase(BaseOSModel):
    persona_id: UUID
    rol_id: UUID
    username: str

class UsuarioCreate(UsuarioBase):
    password: str = PydField(..., min_length=6, description="Clave en texto plano (se transformará en hash)")
    requiere_cambio_password: bool = True
    usuario_auditoria: str

class UsuarioUpdate(BaseOSModel):
    rol_id: Optional[UUID] = None
    password: Optional[str] = PydField(default=None, min_length=6)
    usuario_auditoria: Optional[str] = None

class UsuarioRead(UsuarioBase):
    id: UUID
    requiere_cambio_password: bool
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    usuario_auditoria: Optional[str] = None


class UsuarioResetPasswordRequest(BaseOSModel):
    usuario_auditoria: Optional[str] = None


class UsuarioResetPasswordResponse(BaseOSModel):
    usuario_id: UUID
    username: str
    password_temporal: str
    requiere_cambio_password: bool


class UsuarioVerifyPasswordRequest(BaseOSModel):
    password: str = PydField(..., min_length=1, description="Clave en texto plano a verificar")
