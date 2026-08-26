from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel

from osiris.modules.sri.core_sri.types import FormaPagoSRI


class AgrupacionTendencia(str, Enum):
    DIARIA = "DIARIA"
    MENSUAL = "MENSUAL"
    ANUAL = "ANUAL"


class ReporteVentasResumenRead(BaseModel):
    fecha_inicio: date
    fecha_fin: date
    punto_emision_id: UUID | None = None
    sucursal_id: UUID | None = None
    subtotal_0: Decimal
    subtotal_12: Decimal
    monto_iva: Decimal
    total: Decimal
    total_ventas: int


class ReporteTopProductoRead(BaseModel):
    producto_id: UUID
    nombre_producto: str
    cantidad_vendida: Decimal
    total_dolares_vendido: Decimal
    ganancia_bruta_estimada: Decimal


class ReporteVentasTendenciaRead(BaseModel):
    periodo: date
    total: Decimal
    total_ventas: int


class ReporteVentasPorVendedorRead(BaseModel):
    usuario_id: UUID | None = None
    vendedor: str
    total_vendido: Decimal
    facturas_emitidas: int


class ReporteComprasPorProveedorRead(BaseModel):
    proveedor_id: UUID
    razon_social: str
    total_compras: Decimal
    cantidad_facturas: int


class ReporteMonitorSRIEstadoRead(BaseModel):
    estado: str
    tipo_documento: str
    cantidad: int


class ReporteRentabilidadClienteRead(BaseModel):
    cliente_id: UUID | None = None
    total_vendido: Decimal
    costo_historico_total: Decimal
    utilidad_bruta_dolares: Decimal
    margen_porcentual: Decimal
    total_facturas: int


class ReporteRentabilidadTransaccionRead(BaseModel):
    venta_id: UUID
    cliente_id: UUID | None = None
    fecha_emision: date
    subtotal_venta: Decimal
    costo_historico_total: Decimal
    utilidad_bruta_dolares: Decimal
    margen_porcentual: Decimal


class ReporteImpuestoAgrupadoRead(BaseModel):
    codigo_sri: str
    total_retenido: Decimal


class ReportePre104BloqueRead(BaseModel):
    base_0: Decimal
    base_iva: Decimal
    monto_iva: Decimal
    total: Decimal
    total_documentos: int


class ReporteImpuestosMensualRead(BaseModel):
    mes: int
    anio: int
    sucursal_id: UUID | None = None
    ventas: ReportePre104BloqueRead
    compras: ReportePre104BloqueRead
    retenciones_emitidas: dict[str, Decimal]
    retenciones_recibidas: dict[str, Decimal]


class ReporteInventarioValoracionItemRead(BaseModel):
    producto_id: UUID
    nombre: str
    cantidad_actual: Decimal
    costo_promedio: Decimal
    valor_total: Decimal


class ReporteInventarioValoracionRead(BaseModel):
    patrimonio_total: Decimal
    productos: list[ReporteInventarioValoracionItemRead]


class TipoMovimientoKardex(str, Enum):
    INGRESO = "INGRESO"
    EGRESO = "EGRESO"
    VENTA = "VENTA"


class ReporteInventarioKardexMovimientoRead(BaseModel):
    fecha: date
    tipo_movimiento: TipoMovimientoKardex
    cantidad: Decimal
    costo_unitario: Decimal
    saldo_cantidad: Decimal


class ReporteInventarioKardexRead(BaseModel):
    producto_id: UUID
    fecha_inicio: date
    fecha_fin: date
    movimientos: list[ReporteInventarioKardexMovimientoRead]


class ReporteCarteraCobrarItemRead(BaseModel):
    cliente_id: UUID
    saldo_pendiente: Decimal


class ReporteCarteraPagarItemRead(BaseModel):
    proveedor_id: UUID
    saldo_pendiente: Decimal


class ReporteCajaFormaPagoRead(BaseModel):
    forma_pago_sri: FormaPagoSRI
    monto: Decimal


class ReporteCajaDineroLiquidoRead(BaseModel):
    total: Decimal
    por_forma_pago: list[ReporteCajaFormaPagoRead]


class ReporteCajaCreditoTributarioRead(BaseModel):
    total_retenciones: Decimal


class ReporteCajaCierreDiarioRead(BaseModel):
    fecha: date
    usuario_id: UUID | None = None
    sucursal_id: UUID | None = None
    dinero_liquido: ReporteCajaDineroLiquidoRead
    credito_tributario: ReporteCajaCreditoTributarioRead
