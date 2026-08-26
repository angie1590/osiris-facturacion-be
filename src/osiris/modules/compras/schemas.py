from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, RootModel, computed_field, model_validator

from osiris.modules.sri.core_sri.schemas import (
    IVA_0_CODES,
    IVA_12_CODES,
    IVA_15_CODES,
    IVA_NO_OBJETO_CODES,
    VentaCompraDetalleCreate,
    VentaCompraDetalleRegistroCreate,
    q2,
)
from osiris.modules.sri.core_sri.types import (
    EstadoCompra,
    EstadoCuentaPorPagar,
    EstadoRetencion,
    FormaPagoSRI,
    SustentoTributarioSRI,
    TipoIdentificacionSRI,
    TipoRetencionSRI,
)


class CompraCreate(BaseModel):
    sucursal_id: UUID | None = None
    proveedor_id: UUID
    secuencial_factura: str = Field(..., pattern=r"^\d{3}-\d{3}-\d{9}$")
    autorizacion_sri: str = Field(..., pattern=r"^\d{37}$|^\d{49}$")
    fecha_emision: date = Field(default_factory=date.today)
    bodega_id: UUID | None = None
    sustento_tributario: SustentoTributarioSRI
    tipo_identificacion_proveedor: TipoIdentificacionSRI
    identificacion_proveedor: str = Field(..., min_length=3, max_length=20)
    forma_pago: FormaPagoSRI
    usuario_auditoria: str
    detalles: list[VentaCompraDetalleCreate] = Field(..., min_length=1)

    @computed_field(return_type=Decimal)
    def subtotal_sin_impuestos(self) -> Decimal:
        return q2(sum((d.subtotal_sin_impuesto for d in self.detalles), Decimal("0.00")))

    @computed_field(return_type=Decimal)
    def subtotal_12(self) -> Decimal:
        total = Decimal("0.00")
        for detalle in self.detalles:
            iva = detalle.iva_impuesto()
            if iva and iva.codigo_porcentaje_sri in IVA_12_CODES:
                total += detalle.subtotal_sin_impuesto
        return q2(total)

    @computed_field(return_type=Decimal)
    def subtotal_15(self) -> Decimal:
        total = Decimal("0.00")
        for detalle in self.detalles:
            iva = detalle.iva_impuesto()
            if iva and iva.codigo_porcentaje_sri in IVA_15_CODES:
                total += detalle.subtotal_sin_impuesto
        return q2(total)

    @computed_field(return_type=Decimal)
    def subtotal_0(self) -> Decimal:
        total = Decimal("0.00")
        for detalle in self.detalles:
            iva = detalle.iva_impuesto()
            if iva and iva.codigo_porcentaje_sri in IVA_0_CODES:
                total += detalle.subtotal_sin_impuesto
        return q2(total)

    @computed_field(return_type=Decimal)
    def subtotal_no_objeto(self) -> Decimal:
        total = Decimal("0.00")
        for detalle in self.detalles:
            iva = detalle.iva_impuesto()
            if iva is None or iva.codigo_porcentaje_sri in IVA_NO_OBJETO_CODES:
                total += detalle.subtotal_sin_impuesto
        return q2(total)

    @computed_field(return_type=Decimal)
    def monto_iva(self) -> Decimal:
        total = Decimal("0.00")
        for detalle in self.detalles:
            iva = detalle.iva_impuesto()
            if iva:
                total += detalle.valor_impuesto(iva)
        return q2(total)

    @computed_field(return_type=Decimal)
    def monto_ice(self) -> Decimal:
        total = Decimal("0.00")
        for detalle in self.detalles:
            for ice in detalle.ice_impuestos():
                total += detalle.valor_impuesto(ice)
        return q2(total)

    @computed_field(return_type=Decimal)
    def valor_total(self) -> Decimal:
        return q2(self.subtotal_sin_impuestos + self.monto_iva + self.monto_ice)


class CompraRegistroCreate(BaseModel):
    sucursal_id: UUID | None = None
    proveedor_id: UUID
    secuencial_factura: str = Field(..., pattern=r"^\d{3}-\d{3}-\d{9}$")
    autorizacion_sri: str = Field(..., pattern=r"^\d{37}$|^\d{49}$")
    fecha_emision: date = Field(default_factory=date.today)
    bodega_id: UUID | None = None
    sustento_tributario: SustentoTributarioSRI
    tipo_identificacion_proveedor: TipoIdentificacionSRI
    identificacion_proveedor: str = Field(..., min_length=3, max_length=20)
    forma_pago: FormaPagoSRI
    usuario_auditoria: str
    detalles: list[VentaCompraDetalleRegistroCreate] = Field(..., min_length=1)


class CompraUpdate(BaseModel):
    sucursal_id: UUID | None = None
    secuencial_factura: str | None = Field(default=None, pattern=r"^\d{3}-\d{3}-\d{9}$")
    autorizacion_sri: str | None = Field(default=None, pattern=r"^\d{37}$|^\d{49}$")
    fecha_emision: date | None = None
    sustento_tributario: SustentoTributarioSRI | None = None
    tipo_identificacion_proveedor: TipoIdentificacionSRI | None = None
    identificacion_proveedor: str | None = Field(default=None, min_length=3, max_length=20)
    forma_pago: FormaPagoSRI | None = None
    usuario_auditoria: str


class CompraAnularRequest(BaseModel):
    usuario_auditoria: str


class CompraRead(BaseModel):
    id: UUID
    sucursal_id: UUID | None = None
    proveedor_id: UUID
    secuencial_factura: str
    autorizacion_sri: str
    fecha_emision: date
    sustento_tributario: SustentoTributarioSRI
    tipo_identificacion_proveedor: TipoIdentificacionSRI
    identificacion_proveedor: str
    forma_pago: FormaPagoSRI
    subtotal_sin_impuestos: Decimal
    subtotal_12: Decimal
    subtotal_15: Decimal
    subtotal_0: Decimal
    subtotal_no_objeto: Decimal
    monto_iva: Decimal
    monto_ice: Decimal
    valor_total: Decimal
    estado: EstadoCompra
    creado_en: datetime | None = None
    actualizado_en: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class CuentaPorPagarRead(BaseModel):
    id: UUID
    compra_id: UUID
    valor_total_factura: Decimal
    valor_retenido: Decimal
    pagos_acumulados: Decimal
    saldo_pendiente: Decimal
    estado: EstadoCuentaPorPagar
    creado_en: datetime | None = None
    actualizado_en: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class CuentaPorPagarListItemRead(BaseModel):
    id: UUID
    compra_id: UUID
    proveedor_id: UUID
    proveedor: str
    numero_factura: str
    fecha_emision: date
    valor_total_factura: Decimal
    valor_retenido: Decimal
    pagos_acumulados: Decimal
    saldo_pendiente: Decimal
    estado: EstadoCuentaPorPagar


class PagoCxPCreate(BaseModel):
    monto: Decimal = Field(..., gt=Decimal("0"))
    fecha: date = Field(default_factory=date.today)
    forma_pago: FormaPagoSRI
    usuario_auditoria: str


class PagoCxPRead(BaseModel):
    id: UUID
    cuenta_por_pagar_id: UUID
    monto: Decimal
    fecha: date
    forma_pago: FormaPagoSRI

    model_config = ConfigDict(from_attributes=True)


class PlantillaRetencionDetalleInput(BaseModel):
    codigo_retencion_sri: str = Field(..., min_length=1, max_length=10)
    tipo: TipoRetencionSRI
    porcentaje: Decimal = Field(..., gt=Decimal("0"))

    @model_validator(mode="after")
    def normalizar_porcentaje(self):
        self.porcentaje = q2(self.porcentaje)
        return self


class GuardarPlantillaRetencionRequest(BaseModel):
    usuario_auditoria: str
    nombre: str = Field(default="Plantilla Retencion", min_length=1, max_length=150)
    es_global: bool = False
    detalles: list[PlantillaRetencionDetalleInput] = Field(..., min_length=1)


class PlantillaRetencionDetalleRead(BaseModel):
    id: UUID
    codigo_retencion_sri: str
    tipo: TipoRetencionSRI
    porcentaje: Decimal

    model_config = ConfigDict(from_attributes=True)


class PlantillaRetencionRead(BaseModel):
    id: UUID
    proveedor_id: UUID | None
    nombre: str
    es_global: bool
    detalles: list[PlantillaRetencionDetalleRead]

    model_config = ConfigDict(from_attributes=True)


class RetencionSugeridaDetalleRead(BaseModel):
    codigo_retencion_sri: str
    tipo: TipoRetencionSRI
    porcentaje: Decimal
    base_calculo: Decimal
    valor_retenido: Decimal


class RetencionSugeridaRead(BaseModel):
    compra_id: UUID
    plantilla_id: UUID
    proveedor_id: UUID | None
    detalles: list[RetencionSugeridaDetalleRead]
    total_retenido: Decimal


class RetencionDetalleCreate(BaseModel):
    codigo_retencion_sri: str = Field(..., min_length=1, max_length=10)
    tipo: TipoRetencionSRI
    porcentaje: Decimal = Field(..., gt=Decimal("0"))
    base_calculo: Decimal = Field(..., ge=Decimal("0"))

    @computed_field(return_type=Decimal)
    def valor_retenido(self) -> Decimal:
        return q2(q2(self.base_calculo) * q2(self.porcentaje) / Decimal("100"))


class RetencionCreate(BaseModel):
    fecha_emision: date = Field(default_factory=date.today)
    usuario_auditoria: str
    detalles: list[RetencionDetalleCreate] = Field(..., min_length=1)

    @computed_field(return_type=Decimal)
    def total_retenido(self) -> Decimal:
        return q2(sum((d.valor_retenido for d in self.detalles), Decimal("0.00")))


class RetencionEmitRequest(BaseModel):
    usuario_auditoria: str
    encolar: bool = False


class RetencionDetalleRead(BaseModel):
    id: UUID
    codigo_retencion_sri: str
    tipo: TipoRetencionSRI
    porcentaje: Decimal
    base_calculo: Decimal
    valor_retenido: Decimal

    model_config = ConfigDict(from_attributes=True)


class RetencionRead(BaseModel):
    id: UUID
    compra_id: UUID
    fecha_emision: date
    estado: EstadoRetencion
    estado_sri: str
    sri_intentos: int = 0
    sri_ultimo_error: str | None = None
    total_retenido: Decimal
    detalles: list[RetencionDetalleRead]

    model_config = ConfigDict(from_attributes=True)


class RetencionFEPayloadRead(RootModel[dict[str, Any]]):
    pass
