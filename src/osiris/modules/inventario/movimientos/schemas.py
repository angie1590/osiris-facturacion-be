from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from osiris.modules.inventario.movimientos.models import (
    EstadoMovimientoInventario,
    TipoMovimientoInventario,
)


class MovimientoInventarioDetalleCreate(BaseModel):
    producto_id: UUID
    cantidad: Decimal = Field(..., gt=Decimal("0"))
    costo_unitario: Decimal = Field(..., ge=Decimal("0"))

    @field_validator("cantidad")
    @classmethod
    def validar_cantidad_positiva(cls, value: Decimal) -> Decimal:
        if Decimal(str(value)) <= Decimal("0"):
            raise ValueError("La cantidad debe ser mayor a 0.")
        return Decimal(str(value))


class MovimientoInventarioCreate(BaseModel):
    fecha: date = Field(default_factory=date.today)
    bodega_id: UUID
    tipo_movimiento: TipoMovimientoInventario
    estado: EstadoMovimientoInventario = EstadoMovimientoInventario.BORRADOR
    referencia_documento: str | None = Field(default=None, max_length=120)
    motivo_ajuste: str | None = Field(default=None, max_length=255)
    usuario_auditoria: str | None = None
    detalles: list[MovimientoInventarioDetalleCreate] = Field(..., min_length=1)


class MovimientoInventarioDetalleRead(BaseModel):
    id: UUID
    movimiento_inventario_id: UUID
    producto_id: UUID
    cantidad: Decimal
    costo_unitario: Decimal


class MovimientoInventarioRead(BaseModel):
    id: UUID
    fecha: date
    bodega_id: UUID
    tipo_movimiento: TipoMovimientoInventario
    estado: EstadoMovimientoInventario
    referencia_documento: str | None = None
    motivo_ajuste: str | None = None
    detalles: list[MovimientoInventarioDetalleRead]


class MovimientoInventarioConfirmRequest(BaseModel):
    motivo_ajuste: str | None = Field(default=None, max_length=255)
    usuario_auditoria: str | None = None


class MovimientoInventarioAnularRequest(BaseModel):
    motivo: str = Field(..., min_length=3, max_length=255)
    usuario_auditoria: str | None = None


class TransferenciaInventarioDetalleCreate(BaseModel):
    producto_id: UUID
    cantidad: Decimal = Field(..., gt=Decimal("0"))


class TransferenciaInventarioCreate(BaseModel):
    fecha: date = Field(default_factory=date.today)
    bodega_origen_id: UUID
    bodega_destino_id: UUID
    referencia_documento: str | None = Field(default=None, max_length=120)
    usuario_auditoria: str | None = None
    detalles: list[TransferenciaInventarioDetalleCreate] = Field(..., min_length=1)


class TransferenciaInventarioRead(BaseModel):
    movimiento_egreso_id: UUID
    movimiento_ingreso_id: UUID
    bodega_origen_id: UUID
    bodega_destino_id: UUID
    referencia_documento: str


class KardexMovimientoRead(BaseModel):
    fecha: date
    movimiento_id: UUID
    tipo_movimiento: TipoMovimientoInventario
    referencia_documento: str | None = None
    cantidad_entrada: Decimal
    cantidad_salida: Decimal
    saldo_cantidad: Decimal
    costo_unitario_aplicado: Decimal
    valor_movimiento: Decimal


class KardexResponse(BaseModel):
    producto_id: UUID
    bodega_id: UUID
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    saldo_inicial: Decimal
    movimientos: list[KardexMovimientoRead]


class ValoracionProductoRead(BaseModel):
    producto_id: UUID
    cantidad_actual: Decimal
    costo_promedio_vigente: Decimal
    valor_total: Decimal


class ValoracionBodegaRead(BaseModel):
    bodega_id: UUID
    total_bodega: Decimal
    productos: list[ValoracionProductoRead]


class ValoracionResponse(BaseModel):
    bodegas: list[ValoracionBodegaRead]
    total_global: Decimal
