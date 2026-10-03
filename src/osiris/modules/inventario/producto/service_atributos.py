from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, col, select

from osiris.core.audit import record_domain_change
from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.modules.inventario.atributo.entity import Atributo, TipoDato
from osiris.modules.common.catalogo.entity import CatalogoValor
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
        if tipo_dato in {TipoDato.SELECT, TipoDato.CATALOG}:
            return "valor_string", str(valor).strip()
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

    @staticmethod
    def _json_value(value: Any) -> str | int | float | bool | None:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return value.isoformat() if hasattr(value, "isoformat") else str(value)

    def upsert_valores_producto(
        self,
        session: Session,
        producto_id: UUID,
        valores: list[ProductoAtributoValorUpsert],
        *,
        commit: bool = True,
    ) -> list[ProductoAtributoValor]:
        producto = session.get(Producto, producto_id)
        if not producto or not producto.activo:
            raise HTTPException(status_code=404, detail=f"Producto {producto_id} no encontrado")

        if len({item.atributo_id for item in valores}) != len(valores):
            raise HTTPException(status_code=400, detail="La solicitud contiene atributos duplicados.")

        entities: list[ProductoAtributoValor] = []

        for item in valores:
            atributo = session.get(Atributo, item.atributo_id)
            if not atributo or not atributo.activo:
                raise HTTPException(status_code=404, detail=f"Atributo {item.atributo_id} no encontrado")

            if item.valor is None or (isinstance(item.valor, str) and not item.valor.strip()):
                raise HTTPException(
                    status_code=400,
                    detail=f"El atributo {atributo.nombre} no puede tener un valor vacío.",
                )

            try:
                field_name, cast_value = self._cast_by_tipo(atributo.tipo_dato, item.valor)
                if atributo.tipo_dato == TipoDato.SELECT:
                    options = atributo.select_options or []
                    selected = next(
                        (option for option in options if option.casefold() == str(cast_value).casefold()),
                        None,
                    )
                    if selected is None:
                        raise ValueError("option not configured")
                    cast_value = selected
                elif atributo.tipo_dato == TipoDato.CATALOG:
                    if atributo.catalog_id is None:
                        raise ValueError("catalog not configured")
                    selected = session.exec(
                        select(CatalogoValor.valor).where(
                            col(CatalogoValor.catalogo_id) == atributo.catalog_id,
                            col(CatalogoValor.activo).is_(True),
                            col(CatalogoValor.valor) == str(cast_value),
                        )
                    ).first()
                    if selected is None:
                        raise ValueError("catalog value not active")
                    cast_value = selected
                elif atributo.tipo_dato in {TipoDato.INTEGER, TipoDato.DECIMAL}:
                    numeric_value = Decimal(str(cast_value))
                    if not atributo.allow_negative and numeric_value < 0:
                        raise ValueError("negative values are not allowed")
                    if atributo.min_value is not None and numeric_value < atributo.min_value:
                        raise ValueError("value is below min_value")
                    if atributo.max_value is not None and numeric_value > atributo.max_value:
                        raise ValueError("value is above max_value")
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
                before_value = {}
            else:
                before_value = {
                    "valor_string": entity.valor_string,
                    "valor_integer": entity.valor_integer,
                    "valor_decimal": str(entity.valor_decimal) if entity.valor_decimal is not None else None,
                    "valor_boolean": entity.valor_boolean,
                    "valor_date": entity.valor_date.isoformat() if entity.valor_date is not None else None,
                }

            entity.activo = True
            self._clear_value_columns(entity)
            setattr(entity, field_name, cast_value)
            session.add(entity)
            if isinstance(session, Session):
                record_domain_change(
                    session,
                    entity="tbl_producto_atributo_valor",
                    entity_id=entity.id,
                    action="UPSERT_PRODUCT_ATTRIBUTE_VALUE",
                    before=before_value,
                    after={
                        "producto_id": str(producto_id),
                        "atributo_id": str(item.atributo_id),
                        field_name: self._json_value(cast_value),
                    },
                )
            entities.append(entity)

        if commit:
            session.commit()
            for entity in entities:
                session.refresh(entity)
        else:
            session.flush()
        return entities

    def upsert_valores_producto_validando_aplicabilidad(
        self,
        session: Session,
        producto_id: UUID,
        valores: list[ProductoAtributoValorUpsert],
        *,
        commit: bool = True,
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
        if len({item.atributo_id for item in valores}) != len(valores):
            raise HTTPException(status_code=400, detail="La solicitud contiene atributos duplicados.")

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

        valores_a_guardar = list(valores)
        enviados = {item.atributo_id: item for item in valores_a_guardar}
        for atributo_mapping in atributos_aplicables:
            if atributo_mapping.get("obligatorio") is not True:
                continue
            valor_enviado = enviados.get(atributo_mapping["atributo_id"])
            if valor_enviado is not None:
                if valor_enviado.valor is None or (
                    isinstance(valor_enviado.valor, str) and not valor_enviado.valor.strip()
                ):
                    raise HTTPException(
                        status_code=400,
                        detail=f"El atributo {atributo_mapping['atributo_nombre']} es obligatorio y no puede estar vacío.",
                    )
                continue

            existing = session.exec(
                select(ProductoAtributoValor).where(
                    col(ProductoAtributoValor.producto_id) == producto_id,
                    col(ProductoAtributoValor.atributo_id) == atributo_mapping["atributo_id"],
                    col(ProductoAtributoValor.activo).is_(True),
                )
            ).first()
            if existing is not None:
                continue
            default_value = atributo_mapping.get("valor_default")
            if default_value is None or (isinstance(default_value, str) and not default_value.strip()):
                raise HTTPException(
                    status_code=400,
                    detail=f"El atributo {atributo_mapping['atributo_nombre']} es obligatorio y no tiene valor por defecto.",
                )
            valores_a_guardar.append(
                ProductoAtributoValorUpsert(
                    atributo_id=atributo_mapping["atributo_id"],
                    valor=default_value,
                )
            )

        return self.upsert_valores_producto(session, producto_id, valores_a_guardar, commit=commit)
