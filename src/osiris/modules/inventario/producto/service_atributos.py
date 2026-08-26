from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, select

from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.modules.inventario.atributo.entity import Atributo, TipoDato
from osiris.modules.inventario.categoria.service import CategoriaService
from osiris.modules.inventario.producto.entity import Producto
from osiris.modules.inventario.producto.entity import ProductoCategoria
from osiris.modules.inventario.producto.models_atributos import (
    ProductoAtributoValor,
    ProductoAtributoValorUpsert,
)


class ProductoAtributoValorService:
    @staticmethod
    def _parse_boolean(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and value in (0, 1):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "si", "sí"}:
                return True
            if normalized in {"false", "0", "no"}:
                return False
        raise ValueError("invalid boolean")

    @staticmethod
    def _parse_integer(value: Any) -> int:
        if isinstance(value, bool):
            raise ValueError("invalid integer")
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            if not value.is_integer():
                raise ValueError("invalid integer")
            return int(value)
        if isinstance(value, Decimal):
            if value != value.to_integral_value():
                raise ValueError("invalid integer")
            return int(value)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                raise ValueError("invalid integer")
            if text[0] in {"+", "-"}:
                if text[1:].isdigit():
                    return int(text)
            elif text.isdigit():
                return int(text)
        raise ValueError("invalid integer")

    @staticmethod
    def _parse_decimal(value: Any) -> Decimal:
        if isinstance(value, bool):
            raise ValueError("invalid decimal")
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ValueError("invalid decimal")

    @staticmethod
    def _parse_date(value: Any) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return date.fromisoformat(value.strip())
        raise ValueError("invalid date")

    def _cast_by_tipo(self, tipo_dato: TipoDato, valor: Any) -> tuple[str, Any]:
        if valor is None:
            raise ValueError("null not allowed")

        if tipo_dato == TipoDato.STRING:
            return "valor_string", str(valor)
        if tipo_dato == TipoDato.INTEGER:
            return "valor_integer", self._parse_integer(valor)
        if tipo_dato == TipoDato.DECIMAL:
            return "valor_decimal", self._parse_decimal(valor)
        if tipo_dato == TipoDato.BOOLEAN:
            return "valor_boolean", self._parse_boolean(valor)
        if tipo_dato == TipoDato.DATE:
            return "valor_date", self._parse_date(valor)
        raise ValueError("unsupported type")

    @staticmethod
    def _clear_value_columns(entity: ProductoAtributoValor) -> None:
        entity.valor_string = None
        entity.valor_integer = None
        entity.valor_decimal = None
        entity.valor_boolean = None
        entity.valor_date = None

    def upsert_valores_producto(
        self,
        session: Session,
        producto_id: UUID,
        valores: list[ProductoAtributoValorUpsert],
    ) -> list[ProductoAtributoValor]:
        producto = session.get(Producto, producto_id)
        if not producto or not producto.activo:
            raise HTTPException(status_code=404, detail=f"Producto {producto_id} no encontrado")

        entities: list[ProductoAtributoValor] = []

        for item in valores:
            atributo = session.get(Atributo, item.atributo_id)
            if not atributo or not atributo.activo:
                raise HTTPException(status_code=404, detail=f"Atributo {item.atributo_id} no encontrado")

            try:
                field_name, cast_value = self._cast_by_tipo(atributo.tipo_dato, item.valor)
            except Exception:
                tipo_dato = atributo.tipo_dato.value if hasattr(atributo.tipo_dato, "value") else str(atributo.tipo_dato)
                raise HTTPException(
                    status_code=400,
                    detail=f"Valor incompatible para el atributo {atributo.nombre}. Se esperaba un tipo {tipo_dato}.",
                )

            stmt = (
                select(ProductoAtributoValor)
                .where(ProductoAtributoValor.producto_id == producto_id)
                .where(ProductoAtributoValor.atributo_id == item.atributo_id)
                .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
            )
            entity = session.exec(stmt).first()

            if entity is None:
                entity = ProductoAtributoValor(producto_id=producto_id, atributo_id=item.atributo_id)

            entity.activo = True
            self._clear_value_columns(entity)
            setattr(entity, field_name, cast_value)
            session.add(entity)
            entities.append(entity)

        session.commit()
        for entity in entities:
            session.refresh(entity)
        return entities

    def upsert_valores_producto_validando_aplicabilidad(
        self,
        session: Session,
        producto_id: UUID,
        valores: list[ProductoAtributoValorUpsert],
    ) -> list[ProductoAtributoValor]:
        producto = session.get(Producto, producto_id)
        if not producto or not producto.activo:
            raise HTTPException(status_code=404, detail=f"Producto {producto_id} no encontrado")

        categoria_ids = list(
            session.exec(
                select(ProductoCategoria.categoria_id).where(ProductoCategoria.producto_id == producto_id)
            ).all()
        )
        atributos_aplicables = CategoriaService().get_atributos_heredados_por_categorias(session, categoria_ids)
        atributo_ids_aplicables = {item["atributo_id"] for item in atributos_aplicables}

        for item in valores:
            if item.atributo_id not in atributo_ids_aplicables:
                atributo = session.exec(
                    select(Atributo)
                    .where(Atributo.id == item.atributo_id)
                    .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
                ).first()
                atributo_nombre = atributo.nombre if atributo else "Desconocido"
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"El atributo {atributo_nombre} ({item.atributo_id}) "
                        "no aplica a las categorias actuales del producto."
                    ),
                )

        return self.upsert_valores_producto(session, producto_id, valores)
