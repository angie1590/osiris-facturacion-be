from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, computed_field, model_validator

from osiris.modules.sri.core_sri.types import TipoImpuestoMVP


CENT = Decimal("0.01")
IVA_12_CODES = {"2"}
IVA_15_CODES = {"4"}
IVA_0_CODES = {"0"}
IVA_NO_OBJETO_CODES = {"6"}


def q2(value: Decimal | int | str) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


class ImpuestoAplicadoInput(BaseModel):
    tipo_impuesto: TipoImpuestoMVP
    codigo_impuesto_sri: str = Field(..., min_length=1, max_length=10)
    codigo_porcentaje_sri: str = Field(..., min_length=1, max_length=10)
    tarifa: Decimal = Field(..., ge=Decimal("0"))

    @model_validator(mode="after")
    def validar_codigo_tipo(self):
        if self.tipo_impuesto == TipoImpuestoMVP.IVA and self.codigo_impuesto_sri != "2":
            raise ValueError("Para IVA, codigo_impuesto_sri debe ser '2'.")
        if self.tipo_impuesto == TipoImpuestoMVP.ICE and self.codigo_impuesto_sri != "3":
            raise ValueError("Para ICE, codigo_impuesto_sri debe ser '3'.")
        self.tarifa = q2(self.tarifa)
        return self


class VentaCompraDetalleCreate(BaseModel):
    producto_id: UUID
    descripcion: str = Field(..., min_length=1, max_length=255)
    cantidad: Decimal = Field(..., gt=Decimal("0"))
    precio_unitario: Decimal = Field(..., ge=Decimal("0"))
    descuento: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"))
    es_actividad_excluida: bool = False
    impuestos: list[ImpuestoAplicadoInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def validar_impuestos_por_detalle(self):
        iva_count = sum(1 for i in self.impuestos if i.tipo_impuesto == TipoImpuestoMVP.IVA)
        ice_count = sum(1 for i in self.impuestos if i.tipo_impuesto == TipoImpuestoMVP.ICE)
        if iva_count > 1:
            raise ValueError("Un detalle no puede tener mas de un IVA.")
        if ice_count > 1:
            raise ValueError("Un detalle no puede tener mas de un ICE.")
        self.cantidad = Decimal(str(self.cantidad))
        self.precio_unitario = Decimal(str(self.precio_unitario))
        self.descuento = q2(self.descuento)
        return self

    @computed_field(return_type=Decimal)
    def subtotal_sin_impuesto(self) -> Decimal:
        bruto = Decimal(str(self.cantidad)) * Decimal(str(self.precio_unitario))
        return q2(bruto - self.descuento)

    def monto_ice_detalle(self) -> Decimal:
        total = Decimal("0.00")
        for ice in self.ice_impuestos():
            total += self.valor_impuesto(ice)
        return q2(total)

    def base_imponible_impuesto(self, impuesto: ImpuestoAplicadoInput) -> Decimal:
        base = self.subtotal_sin_impuesto
        if impuesto.tipo_impuesto == TipoImpuestoMVP.IVA:
            base = q2(base + self.monto_ice_detalle())
        return q2(base)

    def valor_impuesto(self, impuesto: ImpuestoAplicadoInput) -> Decimal:
        base = self.base_imponible_impuesto(impuesto)
        return q2(base * impuesto.tarifa / Decimal("100"))

    def iva_impuesto(self) -> Optional[ImpuestoAplicadoInput]:
        for impuesto in self.impuestos:
            if impuesto.tipo_impuesto == TipoImpuestoMVP.IVA:
                return impuesto
        return None

    def ice_impuestos(self) -> list[ImpuestoAplicadoInput]:
        return [i for i in self.impuestos if i.tipo_impuesto == TipoImpuestoMVP.ICE]


class VentaCompraDetalleRegistroCreate(BaseModel):
    producto_id: UUID
    descripcion: str = Field(..., min_length=1, max_length=255)
    cantidad: Decimal = Field(..., gt=Decimal("0"))
    precio_unitario: Decimal = Field(..., ge=Decimal("0"))
    descuento: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"))
    es_actividad_excluida: bool = False
