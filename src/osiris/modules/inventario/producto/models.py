# src/osiris/modules/inventario/producto/models.py
from __future__ import annotations

from datetime import datetime
from datetime import date
from typing import Any, Optional, List
from uuid import UUID
from decimal import Decimal
from pydantic import StrictBool, StrictInt, StrictStr, field_validator

from osiris.domain.base_models import BaseOSModel
from osiris.modules.inventario.producto.entity import TipoProducto as TipoProductoEnum


# Modelos anidados para la respuesta completa
class CasaComercialNested(BaseOSModel):
    nombre: str


class CategoriaNested(BaseOSModel):
    id: UUID
    nombre: str


class ProveedorPersonaNested(BaseOSModel):
    id: UUID
    nombres: str
    apellidos: str
    nombre_comercial: Optional[str] = None


class ProveedorSociedadNested(BaseOSModel):
    id: UUID
    razon_social: str
    nombre_comercial: Optional[str] = None


class AtributoNested(BaseOSModel):
    id: Optional[UUID] = None
    nombre: str
    tipo_dato: Optional[str] = None
    select_options: Optional[List[str]] = None
    catalog_id: Optional[UUID] = None
    allow_negative: bool = False
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None


class AtributoValorNested(BaseOSModel):
    atributo: AtributoNested
    valor: Optional[str | int | Decimal | bool | date] = None
    obligatorio: Optional[bool] = None
    orden: Optional[int] = None

class ImpuestoNested(BaseOSModel):
    id: UUID
    tipo_impuesto: str
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

    @field_validator("impuesto_catalogo_ids")
    @classmethod
    def require_product_tax(cls, values: List[UUID]) -> List[UUID]:
        if not values:
            raise ValueError("Debe seleccionar al menos un impuesto IVA para el producto.")
        return values

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
    impuesto_catalogo_ids: Optional[List[UUID]] = None
    usuario_auditoria: Optional[str] = None

    @field_validator("impuesto_catalogo_ids")
    @classmethod
    def require_nonempty_product_tax_update(cls, values: Optional[List[UUID]]) -> Optional[List[UUID]]:
        if values is not None and not values:
            raise ValueError("El perfil fiscal no puede quedar vacío; seleccione un IVA.")
        return values

    @field_validator("pvp")
    @classmethod
    def validate_pvp_positivo(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v <= 0:
            raise ValueError("El PVP debe ser mayor que cero")
        # Redondear a 2 decimales si se proporciona
        return v.quantize(Decimal("0.01")) if v is not None else None


ProductoAtributoIntegralValue = StrictStr | StrictInt | Decimal | StrictBool | date | None


class ProductoAtributoIntegralInput(BaseOSModel):
    model_config = {"extra": "forbid"}

    atributo_id: UUID
    valor: ProductoAtributoIntegralValue


class ProductoIntegralCreate(BaseOSModel):
    model_config = {"extra": "forbid"}

    nombre: str
    descripcion: Optional[str] = None
    codigo_barras: Optional[str] = None
    tipo: TipoProductoEnum = TipoProductoEnum.BIEN
    pvp: Decimal
    permite_fracciones: bool = False
    casa_comercial_id: Optional[UUID] = None
    categoria_principal_id: UUID
    impuesto_catalogo_ids: List[UUID]
    atributos: List[ProductoAtributoIntegralInput] = []

    @field_validator("impuesto_catalogo_ids")
    @classmethod
    def require_integral_product_tax(cls, values: List[UUID]) -> List[UUID]:
        if not values:
            raise ValueError("Debe seleccionar al menos un impuesto para el producto.")
        return values

    @field_validator("pvp")
    @classmethod
    def validate_integral_pvp(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("El PVP debe ser mayor que cero")
        return value.quantize(Decimal("0.01"))

    @field_validator("atributos")
    @classmethod
    def require_unique_integral_attributes(
        cls, values: List[ProductoAtributoIntegralInput]
    ) -> List[ProductoAtributoIntegralInput]:
        attribute_ids = [item.atributo_id for item in values]
        if len(attribute_ids) != len(set(attribute_ids)):
            raise ValueError("No se puede repetir un atributo en el payload integral.")
        return values


class ProductoIntegralUpdate(BaseOSModel):
    model_config = {"extra": "forbid"}

    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    codigo_barras: Optional[str] = None
    tipo: Optional[TipoProductoEnum] = None
    pvp: Optional[Decimal] = None
    permite_fracciones: Optional[bool] = None
    casa_comercial_id: Optional[UUID] = None
    categoria_principal_id: UUID
    impuesto_catalogo_ids: Optional[List[UUID]] = None
    atributos: Optional[List[ProductoAtributoIntegralInput]] = None
    precondicion_preview: Optional[str] = None

    @field_validator("impuesto_catalogo_ids")
    @classmethod
    def require_nonempty_integral_product_tax_update(
        cls, values: Optional[List[UUID]]
    ) -> Optional[List[UUID]]:
        if values is not None and not values:
            raise ValueError("El perfil fiscal no puede quedar vacío; seleccione un impuesto.")
        return values

    @field_validator("pvp")
    @classmethod
    def validate_integral_update_pvp(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        if value is not None and value <= 0:
            raise ValueError("El PVP debe ser mayor que cero")
        return value.quantize(Decimal("0.01")) if value is not None else None

    @field_validator("atributos")
    @classmethod
    def require_unique_integral_update_attributes(
        cls, values: Optional[List[ProductoAtributoIntegralInput]]
    ) -> Optional[List[ProductoAtributoIntegralInput]]:
        if values is None:
            return None
        attribute_ids = [item.atributo_id for item in values]
        if len(attribute_ids) != len(set(attribute_ids)):
            raise ValueError("No se puede repetir un atributo en el payload integral.")
        return values


class ProductoCambioCategoriaPreviewInput(BaseOSModel):
    model_config = {"extra": "forbid"}

    categoria_principal_id: UUID
    atributos: List[ProductoAtributoIntegralInput] = []


class ProductoCambioCategoriaImpacto(BaseOSModel):
    atributo_id: UUID
    codigo: str
    nombre: str
    valor: Any | None = None
    motivo: str


class ProductoCambioCategoriaPreviewResponse(BaseOSModel):
    operacion: str
    producto_id: UUID
    categoria_actual_id: UUID | None
    categoria_actual_ruta: str | None
    categoria_destino_id: UUID
    categoria_destino_ruta: str
    resumen: str
    conteos: dict[str, int]
    conservados: List[ProductoCambioCategoriaImpacto]
    desactivados: List[ProductoCambioCategoriaImpacto]
    defaults: List[ProductoCambioCategoriaImpacto]
    faltantes: List[ProductoCambioCategoriaImpacto]
    incompatibles: List[ProductoCambioCategoriaImpacto]
    requiere_confirmacion: bool
    acciones_permitidas: List[str]
    precondicion_preview: str


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
    categorias: List[CategoriaNested] = []


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
