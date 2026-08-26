from __future__ import annotations
from enum import Enum
from uuid import UUID
from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field

from osiris.domain.base_models import BaseTable, AuditMixin, SoftDeleteMixin


class TipoDocumentoSRI(str, Enum):
    FACTURA = "FACTURA"
    RETENCION = "RETENCION"
    NOTA_CREDITO = "NOTA_CREDITO"
    NOTA_DEBITO = "NOTA_DEBITO"
    GUIA_REMISION = "GUIA_REMISION"


class PuntoEmision(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_punto_emision"
    __table_args__ = (
        UniqueConstraint("sucursal_id", "codigo", name="uq_pe_sucursal_codigo"),
    )

    codigo: str = Field(nullable=False, max_length=3)
    descripcion: str = Field(nullable=False, max_length=120)
    secuencial_actual: int = Field(default=1, ge=1)
    config_impresion: dict = Field(
        default_factory=lambda: {"margen_superior_cm": 5.0, "max_items_por_pagina": 15},
        sa_column=Column(JSON, nullable=False),
    )

    sucursal_id: UUID = Field(
        foreign_key="tbl_sucursal.id",
        nullable=False,
    )


class PuntoEmisionSecuencial(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_punto_emision_secuencial"
    __table_args__ = (
        UniqueConstraint(
            "punto_emision_id",
            "tipo_documento",
            name="uq_pe_secuencial_punto_tipo_documento",
        ),
    )

    punto_emision_id: UUID = Field(
        foreign_key="tbl_punto_emision.id",
        nullable=False,
        index=True,
    )
    tipo_documento: TipoDocumentoSRI = Field(nullable=False, max_length=40, index=True)
    secuencial_actual: int = Field(default=0, ge=0, nullable=False)
