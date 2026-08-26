from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, RootModel, ValidationInfo, computed_field, model_validator

from osiris.modules.common.empresa.entity import RegimenTributario
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
    EstadoCuentaPorCobrar,
    EstadoRetencionRecibida,
    EstadoSriDocumento,
    EstadoVenta,
    FormaPagoSRI,
    TipoEmisionVenta,
    TipoIdentificacionSRI,
    TipoImpuestoMVP,
)


class VentaCreate(BaseModel):
    cliente_id: UUID | None = None
    empresa_id: UUID | None = None
    punto_emision_id: UUID | None = None
    secuencial_formateado: str | None = Field(default=None, max_length=20)
    fecha_emision: date = Field(default_factory=date.today)
    bodega_id: UUID | None = None
    tipo_identificacion_comprador: TipoIdentificacionSRI
    identificacion_comprador: str = Field(..., min_length=3, max_length=20)
    forma_pago: FormaPagoSRI
    tipo_emision: TipoEmisionVenta | None = None
    regimen_emisor: RegimenTributario = RegimenTributario.GENERAL
    usuario_auditoria: str
    detalles: list[VentaCompraDetalleCreate] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validar_regimen_y_tipo_emision(self):
        if self.regimen_emisor != RegimenTributario.RIMPE_NEGOCIO_POPULAR:
            if self.tipo_emision == TipoEmisionVenta.NOTA_VENTA_FISICA:
                raise ValueError("NOTA_VENTA_FISICA solo está permitido para régimen RIMPE_NEGOCIO_POPULAR.")
            return self

        if self.tipo_emision is None:
            tiene_actividad_excluida = any(d.es_actividad_excluida for d in self.detalles)
            self.tipo_emision = (
                TipoEmisionVenta.ELECTRONICA if tiene_actividad_excluida else TipoEmisionVenta.NOTA_VENTA_FISICA
            )

        for detalle in self.detalles:
            if detalle.es_actividad_excluida:
                continue
            iva = detalle.iva_impuesto()
            if iva and q2(iva.tarifa) > Decimal("0.00"):
                if self.tipo_emision == TipoEmisionVenta.ELECTRONICA:
                    raise ValueError("Los Negocios Populares solo pueden facturar electrónicamente con tarifa 0%")
                raise ValueError(
                    "Los Negocios Populares solo pueden facturar con tarifa 0% de IVA para sus actividades incluyentes"
                )
        return self

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

    @computed_field(return_type=Decimal)
    def total(self) -> Decimal:
        return self.valor_total


class VentaRegistroCreate(BaseModel):
    cliente_id: UUID | None = None
    empresa_id: UUID | None = None
    punto_emision_id: UUID | None = None
    fecha_emision: date = Field(default_factory=date.today)
    bodega_id: UUID | None = None
    tipo_identificacion_comprador: TipoIdentificacionSRI
    identificacion_comprador: str = Field(..., min_length=3, max_length=20)
    forma_pago: FormaPagoSRI
    tipo_emision: TipoEmisionVenta | None = None
    regimen_emisor: RegimenTributario = RegimenTributario.GENERAL
    usuario_auditoria: str
    detalles: list[VentaCompraDetalleRegistroCreate] = Field(..., min_length=1)


class VentaUpdate(BaseModel):
    tipo_identificacion_comprador: TipoIdentificacionSRI | None = None
    identificacion_comprador: str | None = Field(default=None, min_length=3, max_length=20)
    forma_pago: FormaPagoSRI | None = None
    tipo_emision: TipoEmisionVenta | None = None
    usuario_auditoria: str


class VentaEmitRequest(BaseModel):
    usuario_auditoria: str


class VentaAnularRequest(BaseModel):
    usuario_auditoria: str
    confirmado_portal_sri: bool = False
    motivo: str | None = Field(default=None, max_length=500)


class CuentaPorCobrarRead(BaseModel):
    id: UUID
    venta_id: UUID
    valor_total_factura: Decimal
    valor_retenido: Decimal
    pagos_acumulados: Decimal
    saldo_pendiente: Decimal
    estado: EstadoCuentaPorCobrar

    model_config = ConfigDict(from_attributes=True)


class CuentaPorCobrarListItemRead(BaseModel):
    id: UUID
    venta_id: UUID
    cliente_id: UUID | None = None
    cliente: str
    numero_factura: str | None = None
    fecha_emision: date
    valor_total_factura: Decimal
    valor_retenido: Decimal
    pagos_acumulados: Decimal
    saldo_pendiente: Decimal
    estado: EstadoCuentaPorCobrar

    model_config = ConfigDict(from_attributes=True)


class PagoCxCCreate(BaseModel):
    monto: Decimal = Field(..., gt=Decimal("0"))
    fecha: date = Field(default_factory=date.today)
    forma_pago_sri: FormaPagoSRI
    usuario_auditoria: str

    @model_validator(mode="before")
    @classmethod
    def _compat_forma_pago_legacy(cls, data):
        if isinstance(data, dict) and "forma_pago_sri" not in data and "forma_pago" in data:
            data = dict(data)
            data["forma_pago_sri"] = data["forma_pago"]
        return data


class PagoCxCRead(BaseModel):
    id: UUID
    cuenta_por_cobrar_id: UUID
    monto: Decimal
    fecha: date
    forma_pago_sri: FormaPagoSRI

    model_config = ConfigDict(from_attributes=True)


class RetencionRecibidaDetalleCreate(BaseModel):
    codigo_impuesto_sri: str = Field(..., pattern=r"^(1|2)$")
    porcentaje_aplicado: Decimal = Field(..., ge=Decimal("0"))
    base_imponible: Decimal = Field(..., ge=Decimal("0"))
    valor_retenido: Decimal = Field(..., ge=Decimal("0"))

    @model_validator(mode="after")
    def normalizar_montos(self):
        self.porcentaje_aplicado = q2(self.porcentaje_aplicado)
        self.base_imponible = q2(self.base_imponible)
        self.valor_retenido = q2(self.valor_retenido)
        return self


class RetencionRecibidaCreate(BaseModel):
    venta_id: UUID
    cliente_id: UUID
    numero_retencion: str = Field(..., pattern=r"^\d{3}-\d{3}-\d{9}$")
    clave_acceso_sri: str | None = Field(default=None, pattern=r"^\d{49}$")
    fecha_emision: date = Field(default_factory=date.today)
    estado: EstadoRetencionRecibida = EstadoRetencionRecibida.BORRADOR
    usuario_auditoria: str
    detalles: list[RetencionRecibidaDetalleCreate] = Field(..., min_length=1)

    @computed_field(return_type=Decimal)
    def total_retenido(self) -> Decimal:
        return q2(sum((d.valor_retenido for d in self.detalles), Decimal("0.00")))

    @model_validator(mode="after")
    def validar_reglas_tributarias_sri(self, info: ValidationInfo):
        contexto = info.context or {}
        if not contexto:
            return self

        subtotal_general = q2(contexto.get("venta_subtotal_general", Decimal("0.00")))
        monto_iva_factura = q2(contexto.get("venta_monto_iva", Decimal("0.00")))

        for detalle in self.detalles:
            base = q2(detalle.base_imponible)
            if detalle.codigo_impuesto_sri == "1" and base > subtotal_general:
                raise ValueError(
                    "La base imponible de retencion en renta no puede superar el subtotal general de la venta."
                )

            if detalle.codigo_impuesto_sri == "2":
                if monto_iva_factura == Decimal("0.00"):
                    raise ValueError("Es ilegal registrar una retencion de IVA sobre una factura que no genera IVA")
                if base != monto_iva_factura:
                    raise ValueError(
                        "La base imponible de retencion IVA debe ser exactamente igual al monto IVA de la venta."
                    )

        return self


class RetencionRecibidaAnularRequest(BaseModel):
    motivo: str = Field(..., min_length=1, max_length=500)
    usuario_auditoria: str


class RetencionRecibidaDetalleRead(BaseModel):
    id: UUID
    codigo_impuesto_sri: str
    porcentaje_aplicado: Decimal
    base_imponible: Decimal
    valor_retenido: Decimal

    model_config = ConfigDict(from_attributes=True)


class RetencionRecibidaRead(BaseModel):
    id: UUID
    venta_id: UUID
    cliente_id: UUID
    numero_retencion: str
    clave_acceso_sri: str | None
    fecha_emision: date
    estado: EstadoRetencionRecibida
    total_retenido: Decimal
    detalles: list[RetencionRecibidaDetalleRead]

    model_config = ConfigDict(from_attributes=True)


class RetencionRecibidaListItemRead(BaseModel):
    id: UUID
    venta_id: UUID
    cliente_id: UUID
    numero_retencion: str
    fecha_emision: date
    estado: EstadoRetencionRecibida
    total_retenido: Decimal

    model_config = ConfigDict(from_attributes=True)


class VentaDetalleImpuestoRead(BaseModel):
    tipo_impuesto: TipoImpuestoMVP
    codigo_impuesto_sri: str
    codigo_porcentaje_sri: str
    tarifa: Decimal
    base_imponible: Decimal
    valor_impuesto: Decimal


class VentaDetalleRead(BaseModel):
    producto_id: UUID
    descripcion: str
    cantidad: Decimal
    precio_unitario: Decimal
    descuento: Decimal
    subtotal_sin_impuesto: Decimal
    es_actividad_excluida: bool = False
    impuestos: list[VentaDetalleImpuestoRead]


class VentaRead(BaseModel):
    id: UUID
    cliente_id: UUID | None = None
    empresa_id: UUID | None = None
    punto_emision_id: UUID | None = None
    secuencial_formateado: str | None = None
    fecha_emision: date
    tipo_identificacion_comprador: TipoIdentificacionSRI
    identificacion_comprador: str
    forma_pago: FormaPagoSRI
    tipo_emision: TipoEmisionVenta = TipoEmisionVenta.ELECTRONICA
    regimen_emisor: RegimenTributario = RegimenTributario.GENERAL
    estado: EstadoVenta = EstadoVenta.BORRADOR
    estado_sri: EstadoSriDocumento = EstadoSriDocumento.PENDIENTE
    sri_intentos: int = 0
    sri_ultimo_error: str | None = None

    subtotal_sin_impuestos: Decimal
    subtotal_12: Decimal
    subtotal_15: Decimal
    subtotal_0: Decimal
    subtotal_no_objeto: Decimal
    monto_iva: Decimal
    monto_ice: Decimal
    valor_total: Decimal
    total: Decimal | None = None

    detalles: list[VentaDetalleRead]
    creado_en: Optional[datetime] = None
    actualizado_en: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


VentaDetalleImpuestoSnapshotRead = VentaDetalleImpuestoRead


class FEPayloadRead(RootModel[dict[str, Any]]):
    pass


class VentaListItemRead(BaseModel):
    id: UUID
    fecha_emision: date
    cliente_id: UUID | None = None
    cliente: str
    numero_factura: str | None = None
    valor_total: Decimal
    estado: EstadoVenta
    estado_sri: EstadoSriDocumento
    tipo_emision: TipoEmisionVenta

    model_config = ConfigDict(from_attributes=True)
