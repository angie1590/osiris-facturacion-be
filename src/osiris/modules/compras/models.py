from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Column, Numeric, Text
from sqlmodel import Field

from osiris.domain.base_models import AuditMixin, BaseTable, SoftDeleteMixin
from osiris.modules.sri.core_sri.types import (
    EstadoCompra,
    EstadoCuentaPorPagar,
    EstadoRetencion,
    EstadoSriDocumento,
    FormaPagoSRI,
    SustentoTributarioSRI,
    TipoIdentificacionSRI,
    TipoImpuestoMVP,
    TipoRetencionSRI,
)


class Compra(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_compra"

    sucursal_id: UUID | None = Field(default=None, nullable=True, index=True)
    proveedor_id: UUID = Field(nullable=False, index=True)
    secuencial_factura: str = Field(nullable=False, max_length=20, index=True)
    autorizacion_sri: str = Field(nullable=False, max_length=49, index=True)
    fecha_emision: date = Field(default_factory=date.today, nullable=False)
    sustento_tributario: SustentoTributarioSRI = Field(nullable=False, max_length=5)
    tipo_identificacion_proveedor: TipoIdentificacionSRI = Field(nullable=False, max_length=20)
    identificacion_proveedor: str = Field(nullable=False, max_length=20, index=True)
    forma_pago: FormaPagoSRI = Field(nullable=False, max_length=20)

    subtotal_sin_impuestos: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    subtotal_12: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0.00")))
    subtotal_15: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0.00")))
    subtotal_0: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0.00")))
    subtotal_no_objeto: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0.00")))
    monto_iva: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0.00")))
    monto_ice: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0.00")))
    valor_total: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    estado: EstadoCompra = Field(default=EstadoCompra.BORRADOR, nullable=False, max_length=20)


class CompraDetalle(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_compra_detalle"

    compra_id: UUID = Field(foreign_key="tbl_compra.id", nullable=False, index=True)
    producto_id: UUID = Field(foreign_key="tbl_producto.id", nullable=False, index=True)
    descripcion: str = Field(nullable=False, max_length=255)
    cantidad: Decimal = Field(sa_column=Column(Numeric(12, 4), nullable=False))
    precio_unitario: Decimal = Field(sa_column=Column(Numeric(12, 4), nullable=False))
    descuento: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0.00")))
    subtotal_sin_impuesto: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))


class CompraDetalleImpuesto(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_compra_detalle_impuesto"

    compra_detalle_id: UUID = Field(foreign_key="tbl_compra_detalle.id", nullable=False, index=True)
    tipo_impuesto: TipoImpuestoMVP = Field(nullable=False, max_length=10)
    codigo_impuesto_sri: str = Field(nullable=False, max_length=10)
    codigo_porcentaje_sri: str = Field(nullable=False, max_length=10)
    tarifa: Decimal = Field(sa_column=Column(Numeric(7, 4), nullable=False))
    base_imponible: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    valor_impuesto: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))


CompraDetalleImpuestoSnapshot = CompraDetalleImpuesto


class CuentaPorPagar(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_cuenta_por_pagar"

    compra_id: UUID = Field(foreign_key="tbl_compra.id", nullable=False, index=True, unique=True)
    valor_total_factura: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    valor_retenido: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0.00")))
    pagos_acumulados: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0.00")))
    saldo_pendiente: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    estado: EstadoCuentaPorPagar = Field(default=EstadoCuentaPorPagar.PENDIENTE, nullable=False, max_length=20)


class PagoCxP(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_pago_cxp"

    cuenta_por_pagar_id: UUID = Field(foreign_key="tbl_cuenta_por_pagar.id", nullable=False, index=True)
    monto: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    fecha: date = Field(default_factory=date.today, nullable=False, index=True)
    forma_pago: FormaPagoSRI = Field(nullable=False, max_length=20)


class PlantillaRetencion(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_plantilla_retencion"

    proveedor_id: UUID | None = Field(default=None, nullable=True, index=True)
    nombre: str = Field(nullable=False, max_length=150, default="Plantilla Retencion")
    es_global: bool = Field(default=False, nullable=False, index=True)


class PlantillaRetencionDetalle(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_plantilla_retencion_detalle"

    plantilla_retencion_id: UUID = Field(foreign_key="tbl_plantilla_retencion.id", nullable=False, index=True)
    codigo_retencion_sri: str = Field(nullable=False, min_length=1, max_length=10)
    tipo: TipoRetencionSRI = Field(nullable=False, max_length=20)
    porcentaje: Decimal = Field(sa_column=Column(Numeric(7, 4), nullable=False))


class Retencion(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_retencion"

    compra_id: UUID = Field(foreign_key="tbl_compra.id", nullable=False, index=True, unique=True)
    fecha_emision: date = Field(default_factory=date.today, nullable=False, index=True)
    estado: EstadoRetencion = Field(default=EstadoRetencion.BORRADOR, nullable=False, max_length=20)
    estado_sri: EstadoSriDocumento = Field(default=EstadoSriDocumento.PENDIENTE, nullable=False, max_length=20)
    sri_intentos: int = Field(default=0, nullable=False)
    sri_ultimo_error: str | None = Field(default=None, max_length=1000)
    total_retenido: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))


class RetencionDetalle(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_retencion_detalle"

    retencion_id: UUID = Field(foreign_key="tbl_retencion.id", nullable=False, index=True)
    codigo_retencion_sri: str = Field(nullable=False, min_length=1, max_length=10)
    tipo: TipoRetencionSRI = Field(nullable=False, max_length=20)
    porcentaje: Decimal = Field(sa_column=Column(Numeric(7, 4), nullable=False))
    base_calculo: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    valor_retenido: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))


class RetencionEstadoHistorial(BaseTable, table=True):
    __tablename__ = "tbl_retencion_estado_historial"

    entidad_id: UUID = Field(foreign_key="tbl_retencion.id", nullable=False, index=True)
    estado_anterior: str = Field(nullable=False, max_length=30)
    estado_nuevo: str = Field(nullable=False, max_length=30)
    motivo_cambio: str = Field(sa_column=Column(Text, nullable=False))
    usuario_id: str | None = Field(default=None, max_length=255, index=True)
    fecha: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)


class CompraEstadoHistorial(BaseTable, table=True):
    __tablename__ = "tbl_compra_estado_historial"

    entidad_id: UUID = Field(foreign_key="tbl_compra.id", nullable=False, index=True)
    estado_anterior: str = Field(nullable=False, max_length=30)
    estado_nuevo: str = Field(nullable=False, max_length=30)
    motivo_cambio: str = Field(sa_column=Column(Text, nullable=False))
    usuario_id: str | None = Field(default=None, max_length=255, index=True)
    fecha: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)
