from __future__ import annotations

from typing import Any, Literal, Optional
from uuid import UUID
from datetime import datetime
from pydantic import model_validator
from osiris.domain.base_models import BaseOSModel


class CategoriaAtributoUnidadRead(BaseOSModel):
    id: UUID
    codigo: str
    nombre: str
    simbolo: str
    magnitud_codigo: str


class CategoriaAtributoOrigenRead(BaseOSModel):
    id: UUID
    nombre: str


class CategoriaAtributoRestriccionesRead(BaseOSModel):
    allow_negative: bool
    min_value: Any | None = None
    max_value: Any | None = None


class CategoriaAtributoEfectivoRead(BaseOSModel):
    mapping_id: UUID
    atributo_id: UUID
    codigo: str
    nombre: str
    tipo_dato: str
    unidad: CategoriaAtributoUnidadRead | None = None
    restricciones: CategoriaAtributoRestriccionesRead
    select_options: list[str] | None = None
    catalog_id: UUID | None = None
    obligatorio: bool
    valor_default: str | int | float | bool | None = None
    orden: int | None = None
    categoria_origen: CategoriaAtributoOrigenRead
    profundidad: int
    heredado: bool


class CategoriaWriteBase(BaseOSModel):
    model_config = {"extra": "forbid"}

    @model_validator(mode="before")
    @classmethod
    def adapt_legacy_parent_flag(cls, value: Any) -> Any:
        if isinstance(value, dict) and (
            "es_padre" in value or "usuario_auditoria" in value
        ):
            value = value.copy()
            value.pop("es_padre", None)
            value.pop("usuario_auditoria", None)
        return value


class CategoriaBase(CategoriaWriteBase):
    nombre: str
    parent_id: Optional[UUID] = None


class CategoriaCreate(CategoriaBase):
    usuario_auditoria: Optional[str] = None


class CategoriaUpdate(CategoriaWriteBase):
    nombre: Optional[str] = None
    parent_id: Optional[UUID] = None
    confirmar_limpieza_colision: bool = False
    usuario_auditoria: Optional[str] = None


class CategoriaB3CreateConfirmation(BaseOSModel):
    model_config = {"extra": "forbid"}

    confirmar_b3: Literal[True]
    payload: CategoriaCreate
    precondicion_preview: str


class CategoriaB3UpdateConfirmation(BaseOSModel):
    model_config = {"extra": "forbid"}

    confirmar_b3: Literal[True]
    payload: CategoriaUpdate
    precondicion_preview: str


class CategoriaRead(BaseOSModel):
    id: UUID
    nombre: str
    es_padre: bool
    tiene_hijos: bool
    is_default: bool = False
    parent_id: Optional[UUID] = None
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    usuario_auditoria: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def derive_parent_projection(cls, value: Any) -> Any:
        if isinstance(value, dict):
            value = value.copy()
            value.setdefault("tiene_hijos", value.get("es_padre", False))
            return value
        if hasattr(value, "es_padre"):
            values = {
                name: getattr(value, name)
                for name in cls.model_fields
                if name != "tiene_hijos" and hasattr(value, name)
            }
            values["tiene_hijos"] = bool(value.es_padre)
            return values
        return value


class RecategorizarProducto(BaseOSModel):
    producto_id: UUID
    categoria_id: UUID


class RecategorizarProductosRequest(BaseOSModel):
    assignments: list[RecategorizarProducto]
