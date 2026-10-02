from __future__ import annotations
from typing import Optional, Annotated
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, ConfigDict, StringConstraints, Field
from .entity import ModalidadPuntoEmision, TipoDocumentoSRI

Codigo3 = Annotated[str, StringConstraints(pattern=r"^[0-9]{3}$", min_length=3, max_length=3)]

class PuntoEmisionBase(BaseModel):
    codigo: Codigo3
    descripcion: str
    modalidad_emision: ModalidadPuntoEmision = ModalidadPuntoEmision.ELECTRONICA
    secuencial_actual: int = Field(1, ge=1, le=999999999)
    config_impresion: dict[str, float | int] = Field(
        default_factory=lambda: {"margen_superior_cm": 5.0, "max_items_por_pagina": 15}
    )
    usuario_auditoria: Optional[str] = None
    sucursal_id: UUID

class PuntoEmisionCreate(PuntoEmisionBase):
    usuario_auditoria: str

class PuntoEmisionUpdate(BaseModel):
    descripcion: Optional[str] = None
    config_impresion: Optional[dict[str, float | int]] = None
    usuario_auditoria: Optional[str] = None
    activo: Optional[bool] = None

class PuntoEmisionRead(PuntoEmisionBase):
    id: UUID
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    usuario_auditoria: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class PuntoEmisionSecuencialRead(BaseModel):
    id: UUID
    punto_emision_id: UUID
    tipo_documento: TipoDocumentoSRI
    secuencial_actual: int
    usuario_auditoria: Optional[str]
    activo: bool
    creado_en: datetime
    actualizado_en: datetime

    model_config = ConfigDict(from_attributes=True)


class AjusteManualSecuencialRequest(BaseModel):
    usuario_id: UUID
    justificacion: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=500)]
    nuevo_secuencial: int = Field(..., ge=1, le=999999999)


class SiguienteSecuencialRequest(BaseModel):
    usuario_auditoria: Optional[str] = None


class SiguienteSecuencialResponse(BaseModel):
    secuencial: str = Field(..., min_length=9, max_length=9)
    es_previsualizacion: bool = True
