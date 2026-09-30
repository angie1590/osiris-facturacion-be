from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from uuid import UUID

from sqlalchemy import Column, Numeric, Text
from sqlmodel import Field

from osiris.domain.base_models import AuditMixin, BaseTable, SoftDeleteMixin


class EstadoMedidaTemporal(str, Enum):
    BORRADOR = "BORRADOR"
    ACTIVA = "ACTIVA"
    INACTIVA = "INACTIVA"


class TipoComponenteTributario(str, Enum):
    PORCENTUAL = "PORCENTUAL"
    AD_VALOREM = "AD_VALOREM"
    ESPECIFICO = "ESPECIFICO"


class MedidaTributariaTemporal(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_medida_tributaria_temporal"

    empresa_id: UUID = Field(foreign_key="tbl_empresa.id", nullable=False, index=True)
    nombre: str = Field(nullable=False, max_length=180)
    referencia_legal: str = Field(sa_column=Column(Text, nullable=False))
    tipo_impuesto: str = Field(nullable=False, max_length=10)
    componente: TipoComponenteTributario = Field(nullable=False, max_length=20)
    fecha_inicio: date = Field(nullable=False, index=True)
    fecha_fin: date = Field(nullable=False, index=True)
    codigo_impuesto_sri: str = Field(nullable=False, max_length=10)
    codigo_porcentaje_sri: str = Field(nullable=False, max_length=10)
    codigo_sri_confirmado: bool = Field(default=False, nullable=False)
    tarifa: Decimal = Field(sa_column=Column(Numeric(12, 6), nullable=False))
    estado: EstadoMedidaTemporal = Field(default=EstadoMedidaTemporal.BORRADOR, nullable=False, max_length=20)


class MedidaTributariaProducto(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_medida_tributaria_producto"

    medida_id: UUID = Field(foreign_key="tbl_medida_tributaria_temporal.id", nullable=False, index=True)
    producto_id: UUID = Field(foreign_key="tbl_producto.id", nullable=False, index=True)
    # Cantidad de unidad gravable por unidad comercial vendida; obligatoria para ICE específico.
    factor_cantidad: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(14, 8), nullable=True),
    )
    unidad_gravable: str | None = Field(default=None, max_length=40)
