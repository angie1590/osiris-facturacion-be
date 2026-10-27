from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


CodigoUnidad = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z][A-Za-z0-9_]*$",
    ),
]
NombreUnidad = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=120)
]
SimboloUnidad = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=32)
]


class UnidadCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    codigo: CodigoUnidad
    nombre: NombreUnidad
    simbolo: SimboloUnidad
    magnitud_codigo: CodigoUnidad


class UnidadUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    codigo: CodigoUnidad | None = None
    nombre: NombreUnidad | None = None
    simbolo: SimboloUnidad | None = None
    magnitud_codigo: CodigoUnidad | None = None

    @field_validator("codigo", "nombre", "simbolo", "magnitud_codigo")
    @classmethod
    def rechazar_null(cls, valor: str | None) -> str:
        if valor is None:
            raise ValueError("El campo no admite null; omitirlo conserva su valor")
        return valor


class UnidadUsoRead(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    atributos_activos: int = 0
    atributos_inactivos: int = 0
    snapshots_historicos: int = 0


class UnidadRead(UnidadCreate):
    model_config = ConfigDict(extra="forbid", strict=True, from_attributes=True)

    id: UUID
    es_sistema: bool
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    created_by: str | None = None
    updated_by: str | None = None
    usuario_auditoria: str | None = None
    uso: UnidadUsoRead = Field(default_factory=UnidadUsoRead)
