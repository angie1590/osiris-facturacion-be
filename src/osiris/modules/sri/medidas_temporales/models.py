from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from osiris.modules.sri.impuesto_catalogo.entity import TipoImpuesto
from .entity import EstadoMedidaTemporal, TipoComponenteTributario


class MedidaProductoInput(BaseModel):
    producto_id: UUID
    factor_cantidad: Decimal | None = Field(default=None, gt=Decimal("0"))
    unidad_gravable: str | None = Field(default=None, min_length=1, max_length=40)


class MedidaTributariaCreate(BaseModel):
    empresa_id: UUID
    nombre: str = Field(min_length=1, max_length=180)
    referencia_legal: str = Field(min_length=8, max_length=2000)
    tipo_impuesto: TipoImpuesto
    componente: TipoComponenteTributario
    fecha_inicio: date
    fecha_fin: date
    codigo_impuesto_sri: str = Field(min_length=1, max_length=10)
    codigo_porcentaje_sri: str = Field(min_length=1, max_length=10)
    codigo_sri_confirmado: bool = False
    tarifa: Decimal = Field(ge=Decimal("0"), max_digits=12, decimal_places=6)
    productos: list[MedidaProductoInput] = Field(min_length=1)
    usuario_auditoria: str | None = None

    @model_validator(mode="after")
    def validar_medida(self) -> MedidaTributariaCreate:
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError("La fecha final debe ser igual o posterior a la fecha inicial.")
        expected_code = {TipoImpuesto.IVA: "2", TipoImpuesto.ICE: "3"}.get(self.tipo_impuesto)
        if expected_code is None or self.codigo_impuesto_sri != expected_code:
            raise ValueError("El código de impuesto SRI no corresponde al tipo seleccionado.")
        if self.tipo_impuesto == TipoImpuesto.IVA and self.componente != TipoComponenteTributario.PORCENTUAL:
            raise ValueError("Las medidas de IVA deben usar componente porcentual.")
        if self.tipo_impuesto == TipoImpuesto.ICE and self.componente == TipoComponenteTributario.PORCENTUAL:
            raise ValueError("Las medidas de ICE deben indicar componente AD_VALOREM o ESPECIFICO.")
        if self.componente == TipoComponenteTributario.ESPECIFICO:
            if any(not producto.factor_cantidad or not producto.unidad_gravable for producto in self.productos):
                raise ValueError("Cada producto ICE específico requiere factor y unidad gravable.")
        if len({producto.producto_id for producto in self.productos}) != len(self.productos):
            raise ValueError("No se puede repetir un producto en la misma medida.")
        return self


class MedidaTributariaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=180)
    referencia_legal: str | None = Field(default=None, min_length=8, max_length=2000)
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    codigo_porcentaje_sri: str | None = Field(default=None, min_length=1, max_length=10)
    codigo_sri_confirmado: bool | None = None
    tarifa: Decimal | None = Field(default=None, ge=Decimal("0"), max_digits=12, decimal_places=6)
    productos: list[MedidaProductoInput] | None = None
    usuario_auditoria: str | None = None


class MedidaProductoRead(BaseModel):
    producto_id: UUID
    producto_nombre: str
    factor_cantidad: Decimal | None
    unidad_gravable: str | None


class MedidaTributariaRead(BaseModel):
    id: UUID
    empresa_id: UUID
    empresa_nombre: str | None = None
    nombre: str
    referencia_legal: str
    tipo_impuesto: TipoImpuesto
    componente: TipoComponenteTributario
    fecha_inicio: date
    fecha_fin: date
    codigo_impuesto_sri: str
    codigo_porcentaje_sri: str
    codigo_sri_confirmado: bool
    tarifa: Decimal
    estado: EstadoMedidaTemporal
    productos: list[MedidaProductoRead] = Field(default_factory=list)
    creado_en: datetime
    actualizado_en: datetime

    model_config = ConfigDict(from_attributes=True)


class MedidaTributariaCambioEstado(BaseModel):
    estado: EstadoMedidaTemporal
    usuario_auditoria: Optional[str] = None
