from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any
from osiris.domain.service import BaseService
from uuid import UUID
from osiris.core.audit import record_domain_change
from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, col, select

from osiris.modules.common.catalogo.entity import Catalogo
from osiris.modules.common.catalogo.entity import CatalogoValor
from osiris.modules.inventario.producto.models_atributos import (
    ProductoAtributoRemapeo,
    ProductoAtributoValor,
)
from osiris.modules.inventario.producto.service_atributos import ProductoAtributoValorService
from .repository import AtributoRepository
from .entity import Atributo, TipoDato

class AtributoService(BaseService[Atributo]):
    repo = AtributoRepository()

    @staticmethod
    def _value_from_row(
        row: ProductoAtributoValor,
        tipo_dato: TipoDato,
    ) -> str | int | Decimal | bool | date | None:
        if tipo_dato in {TipoDato.STRING, TipoDato.SELECT, TipoDato.CATALOG}:
            return row.valor_string
        if tipo_dato == TipoDato.INTEGER:
            return row.valor_integer
        if tipo_dato == TipoDato.DECIMAL:
            return row.valor_decimal
        if tipo_dato == TipoDato.BOOLEAN:
            return row.valor_boolean
        if tipo_dato == TipoDato.DATE:
            return row.valor_date
        return None

    @staticmethod
    def _json_value(value: Any) -> str | int | float | bool | None:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return str(value.isoformat()) if hasattr(value, "isoformat") else str(value)

    def _convert_existing_values(
        self,
        session: Session,
        attribute: Atributo,
        target: dict[str, Any],
    ) -> tuple[int, list[UUID]]:
        old_type = attribute.tipo_dato
        new_type = target["tipo_dato"]
        if old_type == new_type:
            return 0, []

        rows = list(
            session.exec(
                select(ProductoAtributoValor).where(
                    col(ProductoAtributoValor.atributo_id) == attribute.id,
                    col(ProductoAtributoValor.activo).is_(True),
                )
            ).all()
        )
        value_service = ProductoAtributoValorService()
        converted = 0
        pending_ids: list[UUID] = []
        for row in rows:
            old_value = self._value_from_row(row, old_type)
            try:
                field_name, new_value = value_service._cast_by_tipo(new_type, old_value)
                if new_type == TipoDato.SELECT:
                    matched = next(
                        (option for option in (target.get("select_options") or []) if option.casefold() == str(new_value).casefold()),
                        None,
                    )
                    if matched is None:
                        raise ValueError("value is not in select options")
                    new_value = matched
                elif new_type == TipoDato.CATALOG:
                    catalog_id = target.get("catalog_id")
                    if catalog_id is None:
                        raise ValueError("catalog is missing")
                    matched = session.exec(
                        select(CatalogoValor.valor).where(
                            col(CatalogoValor.catalogo_id) == catalog_id,
                            col(CatalogoValor.activo).is_(True),
                            func.lower(col(CatalogoValor.valor)) == str(new_value).casefold(),
                        )
                    ).first()
                    if matched is None:
                        raise ValueError("value is not active in catalog")
                    new_value = matched
                elif new_type in {TipoDato.INTEGER, TipoDato.DECIMAL}:
                    decimal_value = Decimal(str(new_value))
                    if not target.get("allow_negative", False) and decimal_value < 0:
                        raise ValueError("negative values are not allowed")
                    if target.get("min_value") is not None and decimal_value < target["min_value"]:
                        raise ValueError("below configured minimum")
                    if target.get("max_value") is not None and decimal_value > target["max_value"]:
                        raise ValueError("above configured maximum")
                value_service._clear_value_columns(row)
                setattr(row, field_name, new_value)
                session.add(row)
                converted += 1
            except (ValueError, TypeError, InvalidOperation, KeyError) as exc:
                remap = ProductoAtributoRemapeo(
                    producto_id=row.producto_id,
                    atributo_id=attribute.id,
                    tipo_anterior=old_type.value,
                    tipo_nuevo=new_type.value,
                    valor_anterior={"value": self._json_value(old_value)},
                    motivo=str(exc)[:255],
                    usuario_auditoria="api",
                    activo=True,
                )
                session.add(remap)
                pending_ids.append(remap.id)
                if isinstance(session, Session):
                    record_domain_change(
                        session,
                        entity="tbl_producto_atributo_remapeo",
                        entity_id=remap.id,
                        action="CREATE_ATTRIBUTE_REMAP",
                        before={"valor": self._json_value(old_value), "tipo": old_type.value},
                        after={
                            "producto_id": str(row.producto_id),
                            "atributo_id": str(attribute.id),
                            "tipo_nuevo": new_type.value,
                            "motivo": remap.motivo,
                        },
                    )
        session.flush()
        return converted, pending_ids

    @staticmethod
    def _pluralize_es(name: str) -> str:
        words = name.strip().split()
        if not words:
            return ""
        word = words[-1]
        lowered = word.lower()
        if len(word) > 1 and lowered.endswith(("s", "x")):
            plural = word
        elif lowered.endswith(("a", "e", "i", "o", "u", "á", "é", "í", "ó", "ú")):
            plural = f"{word}s"
        elif lowered.endswith("z"):
            plural = f"{word[:-1]}ces"
        else:
            plural = f"{word}es"
        words[-1] = plural
        return " ".join(words)

    def _normalize_definition(self, session: Session, data: dict[str, Any]) -> dict[str, Any]:
        tipo = data.get("tipo_dato")
        if not isinstance(tipo, TipoDato):
            try:
                tipo = TipoDato(str(tipo).lower())
            except ValueError:
                raise HTTPException(status_code=400, detail="Tipo de dato de atributo no soportado.") from None
        data["tipo_dato"] = tipo

        if tipo == TipoDato.SELECT:
            options = [str(option).strip() for option in (data.get("select_options") or []) if str(option).strip()]
            if not options:
                raise HTTPException(
                    status_code=400,
                    detail={"code": "SELECT_REQUIRES_OPTIONS", "message": "Un atributo select requiere al menos una opción."},
                )
            normalized = [option.casefold() for option in options]
            if len(normalized) != len(set(normalized)):
                raise HTTPException(status_code=400, detail="Las opciones del atributo no pueden repetirse.")
            data["select_options"] = options
            data["catalog_id"] = None
        elif tipo == TipoDato.CATALOG:
            data["select_options"] = None
            catalog_id = data.get("catalog_id")
            if catalog_id is not None:
                catalog = session.get(Catalogo, catalog_id)
                if not catalog or not catalog.activo:
                    raise HTTPException(status_code=404, detail="Catálogo de atributos no encontrado o inactivo.")
            else:
                catalog_name = self._pluralize_es(data.get("nombre", ""))
                catalog = session.exec(
                    select(Catalogo).where(func.lower(Catalogo.nombre) == catalog_name.lower())
                ).first()
                if catalog is None:
                    catalog = Catalogo(nombre=catalog_name, usuario_auditoria="api", activo=True)
                    session.add(catalog)
                    session.flush()
                elif not catalog.activo:
                    catalog.activo = True
                    session.add(catalog)
                data["catalog_id"] = catalog.id
        else:
            data["select_options"] = None
            data["catalog_id"] = None

        numeric_type = tipo in {TipoDato.INTEGER, TipoDato.DECIMAL}
        data["allow_negative"] = bool(data.get("allow_negative", False)) if numeric_type else False
        minimum = data.get("min_value")
        maximum = data.get("max_value")
        if not numeric_type and (minimum is not None or maximum is not None):
            raise HTTPException(status_code=400, detail="Los límites numéricos solo aplican a atributos integer o decimal.")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise HTTPException(status_code=400, detail="min_value no puede ser mayor que max_value.")
        return data

    def create(
        self,
        session: Session,
        data: dict[str, Any],
        *,
        commit: bool = True,
    ) -> Atributo:
        values = self._ensure_dict(data)
        try:
            values = self._normalize_definition(session, values)
            attribute: Atributo = super().create(session, values, commit=False)
            if isinstance(session, Session):
                record_domain_change(
                    session,
                    entity="tbl_atributo",
                    entity_id=attribute.id,
                    action="CREATE_ATTRIBUTE",
                    before={},
                    after={
                        "nombre": attribute.nombre,
                        "tipo_dato": attribute.tipo_dato.value,
                        "catalog_id": str(attribute.catalog_id) if attribute.catalog_id else None,
                    },
                )
            if commit and isinstance(session, Session):
                session.commit()
                session.refresh(attribute)
            return attribute
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    def update(
        self,
        session: Session,
        item_id: UUID,
        data: Any,
        *,
        commit: bool = True,
    ) -> Atributo | None:
        values = self._ensure_dict(data)
        try:
            current = self.repo.get(session, item_id)
            if current is None:
                return None
            merged = {
                "nombre": values.get("nombre", current.nombre),
                "tipo_dato": values.get("tipo_dato", current.tipo_dato),
                "select_options": values.get("select_options", current.select_options),
                "catalog_id": values.get("catalog_id", current.catalog_id),
                "allow_negative": values.get("allow_negative", current.allow_negative),
                "min_value": values.get("min_value", current.min_value),
                "max_value": values.get("max_value", current.max_value),
            }
            normalized = self._normalize_definition(session, merged)
            values.update(normalized)
            converted_count = 0
            pending_remaps: list[UUID] = []
            if isinstance(session, Session) and current.tipo_dato != normalized["tipo_dato"]:
                converted_count, pending_remaps = self._convert_existing_values(session, current, normalized)
            before = {
                "nombre": current.nombre,
                "tipo_dato": current.tipo_dato.value,
                "catalog_id": str(current.catalog_id) if current.catalog_id else None,
            }
            attribute: Atributo | None = super().update(session, item_id, values, commit=False)
            if attribute is None:
                return None
            if isinstance(session, Session):
                record_domain_change(
                    session,
                    entity="tbl_atributo",
                    entity_id=item_id,
                    action="UPDATE_ATTRIBUTE",
                    before=before,
                    after={
                        "nombre": attribute.nombre,
                        "tipo_dato": attribute.tipo_dato.value,
                        "catalog_id": str(attribute.catalog_id) if attribute.catalog_id else None,
                        "converted_values": converted_count,
                        "pending_remap_ids": [str(remap_id) for remap_id in pending_remaps],
                    },
                )
            if commit and isinstance(session, Session):
                session.commit()
                session.refresh(attribute)
            return attribute
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    def delete(self, session: Session, item_id: UUID, *, commit: bool = True) -> bool | None:
        try:
            attribute = self.repo.get(session, item_id)
            if attribute is None:
                return None
            before = {
                "nombre": attribute.nombre,
                "tipo_dato": attribute.tipo_dato.value,
                "activo": attribute.activo,
            }
            deleted = super().delete(session, item_id, commit=False)
            if isinstance(session, Session):
                record_domain_change(
                    session,
                    entity="tbl_atributo",
                    entity_id=item_id,
                    action="DELETE_ATTRIBUTE",
                    before=before,
                    after={"activo": False},
                )
            if commit and isinstance(session, Session):
                session.commit()
            return deleted
        except Exception as exc:
            self._handle_transaction_error(session, exc)
