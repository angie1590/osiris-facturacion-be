from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from uuid import UUID

from sqlalchemy import Column, Numeric, UniqueConstraint
from sqlmodel import Field

from osiris.domain.base_models import AuditMixin, BaseTable, SoftDeleteMixin


class TipoMovimientoInventario(str, Enum):
    INGRESO = "INGRESO"
    EGRESO = "EGRESO"
    TRANSFERENCIA = "TRANSFERENCIA"
    AJUSTE = "AJUSTE"


class EstadoMovimientoInventario(str, Enum):
    BORRADOR = "BORRADOR"
    CONFIRMADO = "CONFIRMADO"
    ANULADO = "ANULADO"


class MovimientoInventario(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_movimiento_inventario"

    fecha: date = Field(default_factory=date.today, nullable=False)
    bodega_id: UUID = Field(foreign_key="tbl_bodega.id", nullable=False, index=True)
    tipo_movimiento: TipoMovimientoInventario = Field(nullable=False, max_length=20)
    estado: EstadoMovimientoInventario = Field(
        default=EstadoMovimientoInventario.BORRADOR,
        nullable=False,
        max_length=20,
    )
    referencia_documento: str | None = Field(default=None, max_length=120)
    motivo_ajuste: str | None = Field(default=None, max_length=255)


class MovimientoInventarioDetalle(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_movimiento_inventario_detalle"

    movimiento_inventario_id: UUID = Field(
        foreign_key="tbl_movimiento_inventario.id",
        nullable=False,
        index=True,
    )
    producto_id: UUID = Field(foreign_key="tbl_producto.id", nullable=False, index=True)
    cantidad: Decimal = Field(sa_column=Column(Numeric(14, 4), nullable=False))
    costo_unitario: Decimal = Field(sa_column=Column(Numeric(14, 4), nullable=False))


class InventarioStock(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_inventario_stock"
    __table_args__ = (
        UniqueConstraint(
            "bodega_id",
            "producto_id",
            name="uq_tbl_inventario_stock_bodega_producto",
        ),
    )

    bodega_id: UUID = Field(foreign_key="tbl_bodega.id", nullable=False, index=True)
    producto_id: UUID = Field(foreign_key="tbl_producto.id", nullable=False, index=True)
    cantidad_actual: Decimal = Field(sa_column=Column(Numeric(14, 4), nullable=False, default=Decimal("0.0000")))
    costo_promedio_vigente: Decimal = Field(
        sa_column=Column(Numeric(14, 4), nullable=False, default=Decimal("0.0000"))
    )
