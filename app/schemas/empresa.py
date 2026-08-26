from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import IdentificationType


class EmpresaCreate(BaseModel):
    ruc: str = Field(..., min_length=10, max_length=13)
    razon_social: str = Field(..., min_length=1, max_length=300)
    nombre_comercial: str | None = Field(None, max_length=300)
    identification_type: IdentificationType = IdentificationType.ruc
    obligado_contabilidad: bool = False


class EmpresaResponse(BaseModel):
    id: int
    ruc: str
    razon_social: str
    nombre_comercial: str | None
    identification_type: IdentificationType
    obligado_contabilidad: bool
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class SucursalCreate(BaseModel):
    codigo_establecimiento: str = Field(..., min_length=3, max_length=3)
    nombre: str = Field(..., min_length=1, max_length=200)
    direccion: str | None = Field(None, max_length=300)


class SucursalResponse(BaseModel):
    id: int
    empresa_id: int
    codigo_establecimiento: str
    nombre: str
    direccion: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class PuntoEmisionCreate(BaseModel):
    codigo_punto_emision: str = Field(..., min_length=3, max_length=3)
    descripcion: str | None = Field(None, max_length=200)


class PuntoEmisionResponse(BaseModel):
    id: int
    sucursal_id: int
    codigo_punto_emision: str
    descripcion: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
