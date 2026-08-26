# src/osiris/modules/inventario/producto/entity.py
from __future__ import annotations

from enum import Enum
from uuid import UUID
from decimal import Decimal
from sqlmodel import Field, Column, Numeric, Relationship
from sqlalchemy.orm import relationship
from osiris.domain.base_models import BaseTable, AuditMixin, SoftDeleteMixin
from osiris.modules.inventario.categoria.entity import Categoria  # noqa: F401
from osiris.modules.sri.impuesto_catalogo.entity import ImpuestoCatalogo  # noqa: F401


class TipoProducto(str, Enum):
    BIEN = "BIEN"
    SERVICIO = "SERVICIO"


class Producto(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_producto"

    nombre: str = Field(index=True, nullable=False, unique=True, max_length=255)
    descripcion: str | None = Field(default=None, max_length=1000)
    codigo_barras: str | None = Field(default=None, max_length=100, index=True)
    tipo: TipoProducto = Field(nullable=False, default=TipoProducto.BIEN)
    pvp: Decimal = Field(
        sa_column=Column(Numeric(10, 2), nullable=False),
        default=Decimal("0.00")
    )
    # Cantidad agregada de inventario (sumatoria de stock materializado por bodegas)
    cantidad: Decimal = Field(
        sa_column=Column(Numeric(14, 4), nullable=False),
        default=Decimal("0.0000"),
    )
    # Define si el producto puede manejar unidades fraccionarias (kg, litros, etc.).
    permite_fracciones: bool = Field(default=False, nullable=False)
    casa_comercial_id: UUID | None = Field(default=None, foreign_key="tbl_casa_comercial.id")

    # Relaciones de lectura para evitar N+1 en listados completos.
    producto_categorias: list = Relationship(
        sa_relationship=relationship("ProductoCategoria", back_populates="producto")
    )
    producto_impuestos: list = Relationship(
        sa_relationship=relationship("ProductoImpuesto", back_populates="producto")
    )

# Puente: Producto-Categoría (solo nodos hoja)
class ProductoCategoria(BaseTable, table=True):
    __tablename__ = "tbl_producto_categoria"

    producto_id: UUID = Field(foreign_key="tbl_producto.id", index=True, nullable=False)
    categoria_id: UUID = Field(foreign_key="tbl_categoria.id", index=True, nullable=False)

    producto: object = Relationship(
        sa_relationship=relationship("Producto", back_populates="producto_categorias")
    )
    categoria: object = Relationship(sa_relationship=relationship("Categoria"))

# Puente: Producto-Proveedor Persona
class ProductoProveedorPersona(BaseTable, table=True):
    __tablename__ = "tbl_producto_proveedor_persona"

    producto_id: UUID = Field(foreign_key="tbl_producto.id", index=True, nullable=False)
    proveedor_persona_id: UUID = Field(foreign_key="tbl_proveedor_persona.id", index=True, nullable=False)

# Puente: Producto-Proveedor Sociedad
class ProductoProveedorSociedad(BaseTable, table=True):
    __tablename__ = "tbl_producto_proveedor_sociedad"

    producto_id: UUID = Field(foreign_key="tbl_producto.id", index=True, nullable=False)
    proveedor_sociedad_id: UUID = Field(foreign_key="tbl_proveedor_sociedad.id", index=True, nullable=False)


# Puente: Producto-Impuesto
class ProductoImpuesto(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_producto_impuesto"

    producto_id: UUID = Field(foreign_key="tbl_producto.id", index=True, nullable=False)
    impuesto_catalogo_id: UUID = Field(foreign_key="aux_impuesto_catalogo.id", index=True, nullable=False)
    codigo_impuesto_sri: str = Field(nullable=False, max_length=10, default="2")
    codigo_porcentaje_sri: str = Field(nullable=False, max_length=10, default="0")
    tarifa: Decimal = Field(
        sa_column=Column(Numeric(7, 4), nullable=False),
        default=Decimal("0.0000"),
    )

    producto: object = Relationship(
        sa_relationship=relationship("Producto", back_populates="producto_impuestos")
    )
    impuesto_catalogo: object = Relationship(sa_relationship=relationship("ImpuestoCatalogo"))

    # Restricción única: un impuesto específico solo se puede asignar una vez a un producto
    # Se implementará en la migración como UNIQUE(producto_id, impuesto_catalogo_id)


# Puente: Producto-Bodega
class ProductoBodega(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_producto_bodega"

    producto_id: UUID = Field(foreign_key="tbl_producto.id", index=True, nullable=False)
    bodega_id: UUID = Field(foreign_key="tbl_bodega.id", index=True, nullable=False)
    cantidad: Decimal = Field(
        sa_column=Column(Numeric(14, 4), nullable=False),
        default=Decimal("0.0000"),
    )  # Cantidad referencial del producto en esta bodega

    # Restricción única: un producto solo puede estar una vez en una bodega
    # Se implementará en la migración como UNIQUE(producto_id, bodega_id)
