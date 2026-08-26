from __future__ import annotations

from enum import Enum
from typing import Optional
from datetime import date
from decimal import Decimal
import sqlalchemy as sa
from sqlmodel import Field, Column, Numeric
from osiris.domain.base_models import BaseTable, AuditMixin, SoftDeleteMixin


class TipoImpuesto(str, Enum):
    IVA = "IVA"
    ICE = "ICE"
    IRBPNR = "IRBPNR"


class ClasificacionIVA(str, Enum):
    GRAVADO = "GRAVADO"
    EXENTO = "EXENTO"
    NO_OBJETO = "NO_OBJETO"
    DIFERENCIADO = "DIFERENCIADO"
    OTRO = "OTRO"


class ModoCalculoICE(str, Enum):
    AD_VALOREM = "AD_VALOREM"
    ESPECIFICO = "ESPECIFICO"
    MIXTO = "MIXTO"


class UnidadBase(str, Enum):
    UNIDAD = "UNIDAD"
    LITRO = "LITRO"
    KILO = "KILO"
    MIL_UNIDADES = "MIL_UNIDADES"
    OTRO = "OTRO"


class AplicaA(str, Enum):
    BIEN = "BIEN"
    SERVICIO = "SERVICIO"
    AMBOS = "AMBOS"


class ImpuestoCatalogo(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "aux_impuesto_catalogo"
    __table_args__ = (
        sa.UniqueConstraint('codigo_sri', 'descripcion', name='uq_impuesto_codigo_descripcion'),
    )

    tipo_impuesto: TipoImpuesto = Field(nullable=False, index=True)
    codigo_tipo_impuesto: str = Field(nullable=False, max_length=10, index=True)  # 2=IVA, 3=ICE, 5=IRBPNR
    codigo_sri: str = Field(nullable=False, max_length=50, index=True)
    descripcion: str = Field(nullable=False, max_length=500)
    vigente_desde: date = Field(nullable=False, index=True)
    vigente_hasta: Optional[date] = Field(default=None, index=True)
    aplica_a: AplicaA = Field(nullable=False)

    # Campos específicos IVA
    porcentaje_iva: Optional[Decimal] = Field(
        default=None,
        sa_column=Column(Numeric(5, 2), nullable=True)
    )
    clasificacion_iva: Optional[ClasificacionIVA] = Field(default=None)

    # Campos específicos ICE
    tarifa_ad_valorem: Optional[Decimal] = Field(
        default=None,
        sa_column=Column(Numeric(5, 2), nullable=True)
    )
    tarifa_especifica: Optional[Decimal] = Field(
        default=None,
        sa_column=Column(Numeric(10, 4), nullable=True)
    )
    modo_calculo_ice: Optional[ModoCalculoICE] = Field(default=None)
    unidad_base: Optional[UnidadBase] = Field(default=None)
