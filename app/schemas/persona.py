from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import IdentificationType
from app.models.persona import TipoPersona


class PersonaCreate(BaseModel):
    tipo: TipoPersona
    identificacion_tipo: IdentificationType = IdentificationType.ruc
    identificacion: str = Field(..., min_length=5, max_length=20)
    razon_social: str = Field(..., min_length=1, max_length=300)
    nombre_comercial: str | None = Field(None, max_length=300)
    email: str | None = Field(None, max_length=100)
    telefono: str | None = Field(None, max_length=20)
    direccion: str | None = Field(None, max_length=300)


class PersonaUpdate(BaseModel):
    razon_social: str | None = Field(None, min_length=1, max_length=300)
    nombre_comercial: str | None = Field(None, max_length=300)
    email: str | None = Field(None, max_length=100)
    telefono: str | None = Field(None, max_length=20)
    direccion: str | None = Field(None, max_length=300)
    is_active: bool | None = None


class PersonaResponse(BaseModel):
    id: int
    empresa_id: int
    tipo: TipoPersona
    identificacion_tipo: IdentificationType
    identificacion: str
    razon_social: str
    nombre_comercial: str | None
    email: str | None
    telefono: str | None
    direccion: str | None
    is_active: bool
    created_at: str

    model_config = ConfigDict(from_attributes=True)
