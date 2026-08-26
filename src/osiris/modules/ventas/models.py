from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Column, Numeric, Text, UniqueConstraint
from sqlmodel import Field

from osiris.domain.base_models import AuditMixin, BaseTable, SoftDeleteMixin
from osiris.modules.common.empresa.entity import RegimenTributario
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


class Venta(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_venta"

    cliente_id: UUID | None = Field(default=None, nullable=True, index=True)
    empresa_id: UUID | None = Field(default=None, foreign_key="tbl_empresa.id", nullable=True, index=True)
    punto_emision_id: UUID | None = Field(default=None, foreign_key="tbl_punto_emision.id", nullable=True, index=True)
    secuencial_formateado: str | None = Field(default=None, max_length=20, nullable=True, index=True)
    fecha_emision: date = Field(default_factory=date.today, nullable=False)
    tipo_identificacion_comprador: TipoIdentificacionSRI = Field(nullable=False, max_length=20)
    identificacion_comprador: str = Field(nullable=False, max_length=20, index=True)
    forma_pago: FormaPagoSRI = Field(nullable=False, max_length=20)
    regimen_emisor: RegimenTributario = Field(default=RegimenTributario.GENERAL, nullable=False)
    tipo_emision: TipoEmisionVenta = Field(default=TipoEmisionVenta.ELECTRONICA, nullable=False, max_length=25)

    subtotal_sin_impuestos: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    subtotal_12: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0.00")))
    subtotal_15: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0.00")))
    subtotal_0: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0.00")))
    subtotal_no_objeto: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0.00")))
    monto_iva: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0.00")))
    monto_ice: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0.00")))
    valor_total: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    estado: EstadoVenta = Field(default=EstadoVenta.BORRADOR, nullable=False, max_length=20)
    estado_sri: EstadoSriDocumento = Field(default=EstadoSriDocumento.PENDIENTE, nullable=False, max_length=20)
    sri_intentos: int = Field(default=0, nullable=False)
    sri_ultimo_error: str | None = Field(default=None, max_length=1000)
    cantidad_impresiones: int = Field(default=0, nullable=False)


class VentaDetalle(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_venta_detalle"

    venta_id: UUID = Field(foreign_key="tbl_venta.id", nullable=False, index=True)
    producto_id: UUID = Field(foreign_key="tbl_producto.id", nullable=False, index=True)
    descripcion: str = Field(nullable=False, max_length=255)
    cantidad: Decimal = Field(sa_column=Column(Numeric(12, 4), nullable=False))
    precio_unitario: Decimal = Field(sa_column=Column(Numeric(12, 4), nullable=False))
    descuento: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0.00")))
    subtotal_sin_impuesto: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    es_actividad_excluida: bool = Field(default=False, nullable=False)


class VentaDetalleImpuesto(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_venta_detalle_impuesto"

    venta_detalle_id: UUID = Field(foreign_key="tbl_venta_detalle.id", nullable=False, index=True)
    tipo_impuesto: TipoImpuestoMVP = Field(nullable=False, max_length=10)
    codigo_impuesto_sri: str = Field(nullable=False, max_length=10)
    codigo_porcentaje_sri: str = Field(nullable=False, max_length=10)
    tarifa: Decimal = Field(sa_column=Column(Numeric(7, 4), nullable=False))
    base_imponible: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    valor_impuesto: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))


VentaDetalleImpuestoSnapshot = VentaDetalleImpuesto


class CuentaPorCobrar(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_cuenta_por_cobrar"

    venta_id: UUID = Field(foreign_key="tbl_venta.id", nullable=False, index=True, unique=True)
    valor_total_factura: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    valor_retenido: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0.00")))
    pagos_acumulados: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0.00")))
    saldo_pendiente: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    estado: EstadoCuentaPorCobrar = Field(default=EstadoCuentaPorCobrar.PENDIENTE, nullable=False, max_length=20)


class PagoCxC(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_pago_cxc"

    cuenta_por_cobrar_id: UUID = Field(foreign_key="tbl_cuenta_por_cobrar.id", nullable=False, index=True)
    monto: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    fecha: date = Field(default_factory=date.today, nullable=False, index=True)
    forma_pago_sri: FormaPagoSRI = Field(nullable=False, max_length=20)


class RetencionRecibida(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_retencion_recibida"
    __table_args__ = (
        UniqueConstraint("cliente_id", "numero_retencion", name="uq_retencion_recibida_cliente_numero"),
    )

    venta_id: UUID = Field(foreign_key="tbl_venta.id", nullable=False, index=True)
    cliente_id: UUID = Field(nullable=False, index=True)
    numero_retencion: str = Field(nullable=False, max_length=20)
    clave_acceso_sri: str | None = Field(default=None, max_length=49, nullable=True, index=True)
    fecha_emision: date = Field(default_factory=date.today, nullable=False, index=True)
    estado: EstadoRetencionRecibida = Field(default=EstadoRetencionRecibida.BORRADOR, nullable=False, max_length=20)
    total_retenido: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))


class RetencionRecibidaDetalle(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_retencion_recibida_detalle"

    retencion_recibida_id: UUID = Field(foreign_key="tbl_retencion_recibida.id", nullable=False, index=True)
    codigo_impuesto_sri: str = Field(nullable=False, max_length=5)
    porcentaje_aplicado: Decimal = Field(sa_column=Column(Numeric(7, 4), nullable=False))
    base_imponible: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    valor_retenido: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))


class VentaEstadoHistorial(BaseTable, table=True):
    __tablename__ = "tbl_venta_estado_historial"

    entidad_id: UUID = Field(foreign_key="tbl_venta.id", nullable=False, index=True)
    estado_anterior: str = Field(nullable=False, max_length=30)
    estado_nuevo: str = Field(nullable=False, max_length=30)
    motivo_cambio: str = Field(sa_column=Column(Text, nullable=False))
    usuario_id: str | None = Field(default=None, max_length=255, index=True)
    fecha: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)


class RetencionRecibidaEstadoHistorial(BaseTable, table=True):
    __tablename__ = "tbl_retencion_recibida_estado_historial"

    entidad_id: UUID = Field(foreign_key="tbl_retencion_recibida.id", nullable=False, index=True)
    estado_anterior: str = Field(nullable=False, max_length=30)
    estado_nuevo: str = Field(nullable=False, max_length=30)
    motivo_cambio: str = Field(sa_column=Column(Text, nullable=False))
    usuario_id: str | None = Field(default=None, max_length=255, index=True)
    fecha: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)
