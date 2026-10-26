from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator
from osiris.domain.base_models import BaseOSModel


class TipoClienteBase(BaseOSModel):
    nombre: str = Field(min_length=1, max_length=255)
    descuento: Decimal = Field(ge=0, le=100)

    @field_validator("nombre", mode="before")
    @classmethod
    def trim_name(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class TipoClienteCreate(TipoClienteBase):
    model_config = {"extra": "forbid", "from_attributes": True}
    usuario_auditoria: Optional[str] = None


class TipoClienteUpdate(BaseOSModel):
    model_config = {"extra": "forbid", "from_attributes": True}
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=255)
    descuento: Optional[Decimal] = Field(default=None, ge=0, le=100)
    usuario_auditoria: Optional[str] = None

    @field_validator("nombre", mode="before")
    @classmethod
    def trim_name(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def reject_null_required(self) -> TipoClienteUpdate:
        if any(
            getattr(self, field) is None
            for field in self.model_fields_set & {"nombre", "descuento"}
        ):
            raise ValueError("nombre y descuento no pueden ser null")
        return self


class TipoClienteRead(TipoClienteBase):
    id: UUID
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    usuario_auditoria: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
