from __future__ import annotations
from enum import Enum
from uuid import UUID
from sqlalchemy import CheckConstraint, JSON, Column, UniqueConstraint
from sqlmodel import Field

from osiris.domain.base_models import BaseTable, AuditMixin, SoftDeleteMixin


class TipoDocumentoSRI(str, Enum):
    FACTURA = "FACTURA"
    RETENCION = "RETENCION"
    NOTA_CREDITO = "NOTA_CREDITO"
    NOTA_DEBITO = "NOTA_DEBITO"
    GUIA_REMISION = "GUIA_REMISION"


class ModalidadPuntoEmision(str, Enum):
    FISICA = "FISICA"
    ELECTRONICA = "ELECTRONICA"


class PuntoEmision(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_punto_emision"
    __table_args__ = (
        UniqueConstraint("sucursal_id", "codigo", name="uq_pe_sucursal_codigo"),
        CheckConstraint("length(codigo) = 3", name="ck_tbl_pe_codigo_length"),
        CheckConstraint("secuencial_actual BETWEEN 1 AND 999999999", name="ck_tbl_pe_secuencial_inicial"),
        CheckConstraint("modalidad_emision IN ('FISICA', 'ELECTRONICA')", name="ck_tbl_pe_modalidad"),
    )

    codigo: str = Field(nullable=False, max_length=3)
    descripcion: str = Field(nullable=False, max_length=120)
    modalidad_emision: ModalidadPuntoEmision = Field(
        default=ModalidadPuntoEmision.ELECTRONICA,
        nullable=False,
        max_length=12,
    )
    # Próximo correlativo inicial/disponible, con rango SRI de nueve dígitos.
    secuencial_actual: int = Field(default=1, ge=1, le=999999999)
    config_impresion: dict[str, float | int] = Field(
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
