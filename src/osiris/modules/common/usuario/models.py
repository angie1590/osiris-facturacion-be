# src/osiris/modules/common/usuario/models.py
from __future__ import annotations
from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import Field as PydField, field_validator
from osiris.core.security import PASSWORD_MIN_LENGTH, validate_password
from osiris.domain.base_models import BaseOSModel
from osiris.modules.common.persona.composition import PersonaReference
from osiris.modules.common.persona.models import PersonaRead


class UsuarioBase(BaseOSModel):
    persona_id: UUID
    rol_id: UUID
    username: str


class UsuarioCreate(PersonaReference):
    rol_id: UUID
    username: str = PydField(min_length=3, max_length=120)
    password: str = PydField(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        description="Clave en texto plano (se transformará en hash)",
    )
    requiere_cambio_password: bool = True
    usuario_auditoria: Optional[str] = None
    model_config = {"extra": "forbid"}

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("password")
    @classmethod
    def password_policy(cls, value: str) -> str:
        return validate_password(value)


class UsuarioUpdate(BaseOSModel):
    persona_id: Optional[UUID] = None
    username: Optional[str] = None
    rol_id: Optional[UUID] = None
    password: Optional[str] = PydField(default=None, min_length=PASSWORD_MIN_LENGTH)
    usuario_auditoria: Optional[str] = None

    model_config = {"extra": "forbid"}


class UsuarioRead(UsuarioBase):
    persona: Optional[PersonaRead] = None
    rol_nombre: Optional[str] = None
    id: UUID
    requiere_cambio_password: bool
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    usuario_auditoria: Optional[str] = None
    tiene_codigo_aprobacion: bool = False


class UsuarioResetPasswordRequest(BaseOSModel):
    usuario_auditoria: Optional[str] = None


class UsuarioResetPasswordResponse(BaseOSModel):
    usuario_id: UUID
    username: str
    password_temporal: str
    requiere_cambio_password: bool


class UsuarioVerifyPasswordRequest(BaseOSModel):
    password: str = PydField(
        ..., min_length=1, description="Clave en texto plano a verificar"
    )


class UsuarioReactivateRequest(BaseOSModel):
    confirmar_empleado_inactivo: bool = False
    usuario_auditoria: Optional[str] = None
