from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Column, Text
from sqlmodel import Field

from osiris.domain.base_models import AuditMixin, BaseTable, SoftDeleteMixin
from osiris.modules.sri.core_sri.types import (
    EstadoColaSri,
    EstadoDocumentoElectronico,
    TipoDocumentoElectronico,
)


class DocumentoElectronico(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_documento_electronico"

    tipo_documento: TipoDocumentoElectronico = Field(
        default=TipoDocumentoElectronico.FACTURA,
        nullable=False,
        max_length=20,
        index=True,
    )
    referencia_id: UUID | None = Field(default=None, nullable=True, index=True)
    venta_id: UUID | None = Field(default=None, foreign_key="tbl_venta.id", nullable=True, index=True)
    clave_acceso: str | None = Field(default=None, max_length=49, nullable=True, index=True)
    estado_sri: EstadoDocumentoElectronico = Field(
        default=EstadoDocumentoElectronico.EN_COLA,
        nullable=False,
        max_length=20,
    )
    estado: EstadoDocumentoElectronico = Field(
        default=EstadoDocumentoElectronico.EN_COLA,
        nullable=False,
        max_length=20,
    )
    mensajes_sri: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    xml_autorizado: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    intentos: int = Field(default=0, nullable=False)
    next_retry_at: datetime | None = Field(default=None, nullable=True, index=True)
    cantidad_impresiones: int = Field(default=0, nullable=False)


class DocumentoElectronicoHistorial(BaseTable, table=True):
    __tablename__ = "tbl_documento_electronico_historial"

    entidad_id: UUID = Field(foreign_key="tbl_documento_electronico.id", nullable=False, index=True)
    estado_anterior: str = Field(nullable=False, max_length=30)
    estado_nuevo: str = Field(nullable=False, max_length=30)
    motivo_cambio: str = Field(sa_column=Column(Text, nullable=False))
    usuario_id: str | None = Field(default=None, max_length=255, index=True)
    fecha: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)


class DocumentoSriCola(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_documento_sri_cola"

    entidad_id: UUID = Field(nullable=False, index=True)
    tipo_documento: str = Field(nullable=False, max_length=30, index=True)
    estado: EstadoColaSri = Field(default=EstadoColaSri.PENDIENTE, nullable=False, max_length=30)
    intentos_realizados: int = Field(default=0, nullable=False)
    max_intentos: int = Field(default=3, nullable=False)
    proximo_intento_en: datetime | None = Field(default=None, nullable=True, index=True)
    ultimo_error: str | None = Field(default=None, max_length=1000)
    payload_json: str = Field(sa_column=Column(Text, nullable=False))
