# src/osiris/modules/inventario/producto/models.py
from __future__ import annotations

from datetime import datetime
from datetime import date
from typing import Optional, List
from uuid import UUID
from decimal import Decimal
from pydantic import field_validator

from osiris.domain.base_models import BaseOSModel
from osiris.modules.inventario.producto.entity import TipoProducto as TipoProductoEnum


# Modelos anidados para la respuesta completa
class CasaComercialNested(BaseOSModel):
    nombre: str


class CategoriaNested(BaseOSModel):
    id: UUID
    nombre: str


class ProveedorPersonaNested(BaseOSModel):
    nombres: str
    apellidos: str
    nombre_comercial: Optional[str] = None


class ProveedorSociedadNested(BaseOSModel):
    razon_social: str
    nombre_comercial: Optional[str] = None


class AtributoNested(BaseOSModel):
    id: Optional[UUID] = None
    nombre: str
    tipo_dato: Optional[str] = None


class AtributoValorNested(BaseOSModel):
    atributo: AtributoNested
    valor: Optional[str | int | Decimal | bool | date] = None
    obligatorio: Optional[bool] = None
    orden: Optional[int] = None

class ImpuestoNested(BaseOSModel):
    nombre: str
    codigo: str
    porcentaje: Decimal


class BodegaNested(BaseOSModel):
    codigo_bodega: str
    nombre_bodega: str


class ProductoCreate(BaseOSModel):
    nombre: str
    descripcion: Optional[str] = None
    codigo_barras: Optional[str] = None
    tipo: TipoProductoEnum = TipoProductoEnum.BIEN
    pvp: Decimal
    permite_fracciones: bool = False
    casa_comercial_id: Optional[UUID] = None
    categoria_ids: Optional[List[UUID]] = None
    impuesto_catalogo_ids: List[UUID]  # OBLIGATORIO: al menos un impuesto IVA
    usuario_auditoria: Optional[str] = None

    @field_validator("pvp")
    @classmethod
    def validate_pvp_positivo(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("El PVP debe ser mayor que cero")
        # Redondear a 2 decimales
        return v.quantize(Decimal("0.01"))


class ProductoUpdate(BaseOSModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    codigo_barras: Optional[str] = None
    tipo: Optional[TipoProductoEnum] = None
    pvp: Optional[Decimal] = None
    permite_fracciones: Optional[bool] = None
    casa_comercial_id: Optional[UUID] = None
    categoria_ids: Optional[List[UUID]] = None
    usuario_auditoria: Optional[str] = None

    @field_validator("pvp")
    @classmethod
    def validate_pvp_positivo(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v <= 0:
            raise ValueError("El PVP debe ser mayor que cero")
        # Redondear a 2 decimales si se proporciona
        return v.quantize(Decimal("0.01")) if v is not None else None


class ProductoRead(BaseOSModel):
    id: UUID
    nombre: str
    descripcion: Optional[str] = None
    codigo_barras: Optional[str] = None
    tipo: TipoProductoEnum
    pvp: Decimal
    cantidad: Decimal
    permite_fracciones: bool
    casa_comercial_id: Optional[UUID] = None
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    usuario_auditoria: Optional[str] = None


class ProductoListadoRead(BaseOSModel):
    id: UUID
    nombre: str
    tipo: TipoProductoEnum
    pvp: Decimal
    cantidad: Decimal


class ProductoCompletoRead(BaseOSModel):
    """Contrato de respuesta completa de producto"""
    id: UUID
    nombre: str
    tipo: TipoProductoEnum
    pvp: Decimal
    cantidad: Decimal
    permite_fracciones: bool
    casa_comercial: Optional[CasaComercialNested] = None
    categorias: List[CategoriaNested] = []
    proveedores_persona: List[ProveedorPersonaNested] = []
    proveedores_sociedad: List[ProveedorSociedadNested] = []
    atributos: List[AtributoValorNested] = []
    impuestos: List[ImpuestoNested] = []
    bodegas: List[BodegaNested] = []
