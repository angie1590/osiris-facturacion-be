from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from osiris.modules.sri.core_sri.types import EstadoDocumentoElectronico, TipoDocumentoElectronico


class FEProcesarColaRead(BaseModel):
    procesados: int = Field(ge=0)


class FEDocumentoColaRead(BaseModel):
    id: UUID
    tipo_documento: TipoDocumentoElectronico
    referencia_id: UUID | None = None
    venta_id: UUID | None = None
    clave_acceso: str | None = None
    estado_sri: EstadoDocumentoElectronico
    intentos: int
    next_retry_at: datetime | None = None
    mensajes_sri: str | None = None
    creado_en: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class FEProcesarDocumentosRequest(BaseModel):
    documento_ids: list[UUID] = Field(default_factory=list)
    procesar_todos: bool = False
    incluir_no_vencidos: bool = True
    tipo_documento: TipoDocumentoElectronico = TipoDocumentoElectronico.FACTURA


class FEProcesarDocumentosRead(BaseModel):
    procesados: int = Field(ge=0)
    ids_procesados: list[UUID] = Field(default_factory=list)
    errores: list[str] = Field(default_factory=list)
