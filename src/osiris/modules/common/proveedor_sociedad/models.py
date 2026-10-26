from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from pydantic import EmailStr, TypeAdapter, field_validator, model_validator
from sqlmodel import Field

from osiris.domain.base_models import BaseOSModel
from osiris.modules.common.persona.models import PersonaCreate, PersonaRead


class ProveedorSociedadBase(BaseOSModel):
    ruc: str = Field(min_length=13, max_length=13)
    razon_social: str = Field(min_length=1)
    nombre_comercial: Optional[str] = None
    direccion: str = Field(min_length=1)
    telefono: Optional[str] = None
    email: EmailStr
    tipo_contribuyente_id: str = Field(min_length=2, max_length=2)

    @field_validator(
        "ruc",
        "razon_social",
        "direccion",
        "email",
        "nombre_comercial",
        "telefono",
        mode="before",
    )
    @classmethod
    def trim_text(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator("telefono")
    @classmethod
    def optional_phone(cls, value: str | None) -> str | None:
        if not value:
            return None
        if len(value) != 10 or not value.isdigit():
            raise ValueError("El telefono debe tener 10 digitos")
        return value

    @field_validator("ruc")
    @classmethod
    def _ruc_len(cls, v: str) -> str:
        if len(v) != 13:
            raise ValueError("El RUC debe tener 13 dígitos")
        return v


class ProveedorSociedadCreate(ProveedorSociedadBase):
    model_config = {"extra": "forbid", "from_attributes": True}
    persona_contacto_id: Optional[UUID] = None
    persona_contacto_nueva: Optional[PersonaCreate] = None
    usuario_auditoria: Optional[str] = None

    @model_validator(mode="after")
    def validate_contact(self) -> ProveedorSociedadCreate:
        if (self.persona_contacto_id is None) == (self.persona_contacto_nueva is None):
            raise ValueError(
                "Enviar exactamente persona_contacto_id o persona_contacto_nueva"
            )
        return self


class ProveedorSociedadUpdate(BaseOSModel):
    model_config = {"extra": "forbid", "from_attributes": True}
    ruc: Optional[str] = None
    razon_social: Optional[str] = None
    nombre_comercial: Optional[str] = None
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    tipo_contribuyente_id: Optional[str] = None
    persona_contacto_id: Optional[UUID] = None
    persona_contacto_nueva: Optional[PersonaCreate] = None
    usuario_auditoria: Optional[str] = None

    @model_validator(mode="after")
    def validate_changes(self) -> ProveedorSociedadUpdate:
        if (
            self.persona_contacto_id is not None
            and self.persona_contacto_nueva is not None
        ):
            raise ValueError("Enviar solo una alternativa de contacto")
        if (
            self.model_fields_set & {"persona_contacto_id", "persona_contacto_nueva"}
            and self.persona_contacto_id is None
            and self.persona_contacto_nueva is None
        ):
            raise ValueError("El contacto no puede ser null")
        for field in self.model_fields_set & {
            "ruc",
            "razon_social",
            "direccion",
            "email",
            "tipo_contribuyente_id",
        }:
            if getattr(self, field) is None:
                raise ValueError(f"{field} no puede ser null")
        changes = {field: getattr(self, field) for field in self.model_fields_set}
        for field in (
            "ruc",
            "razon_social",
            "direccion",
            "email",
            "nombre_comercial",
            "telefono",
        ):
            if isinstance(changes.get(field), str):
                setattr(self, field, changes[field].strip())
        for field in ("razon_social", "direccion"):
            if field in changes and not getattr(self, field):
                raise ValueError(f"{field} no puede ser vacio")
        if "email" in changes:
            self.email = str(TypeAdapter(EmailStr).validate_python(self.email))
        if "telefono" in changes:
            self.telefono = ProveedorSociedadBase.optional_phone(self.telefono)
        ruc = self.ruc
        if "ruc" in changes and (ruc is None or len(ruc) != 13 or not ruc.isdigit()):
            raise ValueError("El RUC debe tener 13 digitos")
        return self


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
    usuario_auditoria: Optional[str] = None
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    persona: Optional[PersonaRead] = None
    tipo_contribuyente_nombre: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
