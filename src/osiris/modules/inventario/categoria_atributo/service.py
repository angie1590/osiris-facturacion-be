# src/osiris/modules/inventario/categoria_atributo/service.py
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional
from uuid import UUID
from collections import defaultdict
from fastapi import HTTPException
from sqlalchemy import (
    Boolean,
    Date,
    Integer,
    Numeric,
    String,
    cast,
    func,
    insert as sa_insert,
    literal,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import Session, col, select
from sqlmodel import SQLModel

from osiris.modules.inventario.atributo.entity import Atributo, TipoDato
from osiris.modules.common.catalogo.entity import CatalogoValor
from osiris.core.audit import record_domain_change
from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.inventario.categoria.resolver import (
    get_effective_attributes_by_category,
    resolve_unambiguous_category_scope,
)
from osiris.modules.inventario.producto.entity import Producto
from osiris.modules.inventario.producto.models_atributos import (
    ProductoAtributoRemapeo,
    ProductoAtributoValor,
)
from .models import CategoriaAtributoCreate, CategoriaAtributoUpdate


class CategoriaAtributoService:
    @staticmethod
    def _already_assigned() -> HTTPException:
        return HTTPException(
            status_code=409,
            detail={
                "code": "ATTRIBUTE_ALREADY_ASSIGNED",
                "message": "El atributo ya esta asignado a la categoria. "
                "Si la asignacion esta inactiva, reactiva la existente.",
                "acciones_permitidas": ["reactivar"],
                "conteos": {},
            },
        )

    def _validar_asignacion_historica(
        self, session: Session, categoria_id: UUID, atributo_id: UUID
    ) -> None:
        if not isinstance(session, Session):
            return
        existing = session.exec(
            select(col(CategoriaAtributo.id))
            .where(
                col(CategoriaAtributo.categoria_id) == categoria_id,
                col(CategoriaAtributo.atributo_id) == atributo_id,
            )
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
            .limit(1)
        ).first()
        if existing is not None:
            raise self._already_assigned()

    @staticmethod
    def _raise_integrity(error: IntegrityError) -> None:
        constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
        message = str(error.orig)
        if (
            constraint == "uq_categoria_atributo_historical"
            or "uq_categoria_atributo_historical" in message
            or "UNIQUE constraint failed: tbl_categoria_atributo.categoria_id, "
            "tbl_categoria_atributo.atributo_id" in message
        ):
            raise CategoriaAtributoService._already_assigned() from error
        raise error

    @staticmethod
    def _validar_nombre_unico_global(
        session: Session,
        categoria_id: UUID,
        atributo_id: UUID,
    ) -> None:
        if not isinstance(session, Session):
            return

        categoria = session.get(Categoria, categoria_id)
        atributo = session.get(Atributo, atributo_id)
        if not categoria or not categoria.activo:
            raise HTTPException(
                status_code=404, detail="Categoría no encontrada o inactiva."
            )
        if not atributo or not atributo.activo:
            raise HTTPException(
                status_code=404, detail="Atributo no encontrado o inactivo."
            )

        normalized_name = atributo.nombre.strip().casefold()
        existing_attribute_id = session.exec(
            select(col(Atributo.id))
            .where(
                col(Atributo.activo).is_(True),
                col(Atributo.id) != atributo_id,
                func.lower(func.trim(col(Atributo.nombre))) == normalized_name,
            )
            .limit(1)
        ).first()
        if existing_attribute_id is not None:
            raise HTTPException(
                status_code=409,
                detail="Ya existe un atributo activo con ese nombre en otra categoría.",
            )

    @staticmethod
    def _is_empty_default(value: Optional[str]) -> bool:
        return value is None or (isinstance(value, str) and value.strip() == "")

    @staticmethod
    def _invalid_default() -> HTTPException:
        return HTTPException(
            status_code=422,
            detail={
                "code": "DEFAULT_VALUE_INVALID",
                "message": "El valor por defecto no cumple la definición del atributo.",
            },
        )

    def _validate_default(
        self, session: Session, attribute: Optional[Atributo], value: object
    ) -> str:
        if attribute is None or value is None or (
            isinstance(value, str) and not value.strip()
        ):
            raise self._invalid_default()
        try:
            cast_value, kind = self._cast_default_by_tipo(
                str(value), attribute.tipo_dato
            )
            if kind == TipoDato.SELECT.value:
                options = attribute.select_options or []
                canonical = next(
                    (
                        option
                        for option in options
                        if option.casefold() == str(cast_value).casefold()
                    ),
                    None,
                )
                if canonical is None:
                    raise ValueError("unconfigured option")
                return canonical
            if kind == TipoDato.CATALOG.value:
                if attribute.catalog_id is None:
                    raise ValueError("catalog is missing")
                canonical = session.exec(
                    select(CatalogoValor.valor).where(
                        col(CatalogoValor.catalogo_id) == attribute.catalog_id,
                        col(CatalogoValor.activo).is_(True),
                        col(CatalogoValor.valor) == str(cast_value),
                    )
                ).first()
                if canonical is None:
                    raise ValueError("inactive catalog value")
                return str(canonical)
            if kind in {TipoDato.INTEGER.value, TipoDato.DECIMAL.value}:
                numeric_value = Decimal(str(cast_value))
                if (
                    not numeric_value.is_finite()
                    or (not attribute.allow_negative and numeric_value < 0)
                    or (
                        attribute.min_value is not None
                        and numeric_value < attribute.min_value
                    )
                    or (
                        attribute.max_value is not None
                        and numeric_value > attribute.max_value
                    )
                ):
                    raise ValueError("numeric bounds")
                return str(cast_value)
            if kind == TipoDato.BOOLEAN.value:
                return "true" if cast_value else "false"
            if kind == TipoDato.DATE.value:
                if isinstance(cast_value, date):
                    return cast_value.isoformat()
                raise ValueError("invalid date")
            return str(cast_value)
        except (HTTPException, ValueError, TypeError, InvalidOperation):
            raise self._invalid_default() from None

    @staticmethod
    def _parse_bool(value: str) -> bool:
        normalized = value.strip().lower()
        if normalized in {"true", "1", "t", "yes", "y"}:
            return True
        if normalized in {"false", "0", "f", "no", "n"}:
            return False
        raise ValueError("Valor booleano inválido")

    @staticmethod
    def _normalize_tipo_dato(tipo_dato: Optional[object]) -> Optional[str]:
        if tipo_dato is None:
            return None
        if hasattr(tipo_dato, "value"):
            return str(tipo_dato.value).lower()
        return str(tipo_dato).lower()

    def _cast_default_by_tipo(
        self,
        valor_default: str,
        tipo_dato: Optional[object],
    ) -> tuple[str | int | Decimal | bool | date, str]:
        tipo_normalizado = self._normalize_tipo_dato(tipo_dato)
        if tipo_normalizado is None:
            raise HTTPException(
                status_code=400,
                detail="No se pudo determinar el tipo de dato del atributo",
            )

        try:
            if tipo_normalizado in {
                TipoDato.STRING.value,
                TipoDato.SELECT.value,
                TipoDato.CATALOG.value,
            }:
                return str(valor_default), tipo_normalizado
            if tipo_normalizado == TipoDato.INTEGER.value:
                return int(str(valor_default).strip()), tipo_normalizado
            if tipo_normalizado == TipoDato.DECIMAL.value:
                return Decimal(str(valor_default).strip()), tipo_normalizado
            if tipo_normalizado == TipoDato.BOOLEAN.value:
                return self._parse_bool(str(valor_default)), tipo_normalizado
            if tipo_normalizado == TipoDato.DATE.value:
                return date.fromisoformat(str(valor_default).strip()), tipo_normalizado
        except (ValueError, TypeError, InvalidOperation):
            raise HTTPException(
                status_code=400,
                detail="El valor_default no coincide con el tipo de dato del atributo",
            ) from None

        raise HTTPException(
            status_code=400, detail="Tipo de dato del atributo no soportado"
        )

    def _ejecutar_backfill_atributo(
        self,
        session: Session,
        categoria_atributo: CategoriaAtributo,
        tipo_dato: Optional[object],
    ) -> None:
        """
        Backfill masivo (sin loops Python):
        - productos de categoría origen y descendientes via CTE recursivo
        - INSERT ... SELECT tipado
        - ON CONFLICT DO NOTHING por (producto_id, atributo_id)
        """
        if not isinstance(session, Session):
            return
        valor_default = categoria_atributo.valor_default
        if valor_default is None or self._is_empty_default(valor_default):
            return

        valor_tipado, tipo_normalizado = self._cast_default_by_tipo(
            valor_default, tipo_dato
        )

        categorias_cte = (
            select(col(Categoria.id).label("categoria_id"))
            .where(
                col(Categoria.id) == categoria_atributo.categoria_id,
                col(Categoria.activo).is_(True),
            )
            .cte(name="categoria_descendientes", recursive=True)
        )
        categorias_cte = categorias_cte.union_all(
            select(col(Categoria.id).label("categoria_id")).where(
                col(Categoria.parent_id) == categorias_cte.c.categoria_id,
                col(Categoria.activo).is_(True),
            )
        )

        descendant_ids = list(
            session.exec(select(categorias_cte.c.categoria_id)).all()
        )
        effective_by_category = get_effective_attributes_by_category(
            session, descendant_ids
        )
        effective_category_ids = [
            category_id
            for category_id, attributes in effective_by_category.items()
            if any(
                attribute["mapping_id"] == categoria_atributo.id
                for attribute in attributes
            )
        ]
        if not effective_category_ids:
            return

        descendants = (
            select(
                col(Categoria.id).label("source_category_id"),
                col(Categoria.id).label("descendant_id"),
                literal(0).label("depth"),
                (literal("|") + cast(col(Categoria.id), String) + literal("|")).label(
                    "path"
                ),
            )
            .where(
                col(Categoria.id).in_(effective_category_ids),
                col(Categoria.activo).is_(True),
            )
            .cte(name="backfill_category_descendants", recursive=True)
        )
        child_category = aliased(Categoria, name="backfill_descendant_category")
        descendants = descendants.union_all(
            select(
                descendants.c.source_category_id,
                col(child_category.id),
                (descendants.c.depth + 1).label("depth"),
                (
                    descendants.c.path
                    + cast(col(child_category.id), String)
                    + literal("|")
                ).label("path"),
            )
            .join(
                child_category,
                col(child_category.parent_id) == descendants.c.descendant_id,
            )
            .where(
                col(child_category.activo).is_(True),
                descendants.c.path.not_like(
                    literal("%|")
                    + cast(col(child_category.id), String)
                    + literal("|%")
                ),
            )
        )
        eligible_products = (
            select(col(Producto.id).label("producto_id"))
            .where(
                col(Producto.categoria_principal_id).in_(effective_category_ids),
                col(Producto.activo).is_(True),
            )
            .distinct()
            .subquery()
        )
        candidate_product_ids = list(
            session.exec(
                select(eligible_products.c.producto_id)
            ).all()
        )
        attribute = session.get(Atributo, categoria_atributo.atributo_id)
        existing_rows = session.exec(
            select(ProductoAtributoValor)
            .where(
                col(ProductoAtributoValor.producto_id).in_(candidate_product_ids),
                col(ProductoAtributoValor.atributo_id)
                == categoria_atributo.atributo_id,
            )
            .with_for_update()
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        ).all() if candidate_product_ids else []
        existing_product_ids: set[UUID] = set()
        for row in existing_rows:
            existing_product_ids.add(row.producto_id)
            if row.activo:
                continue
            previous_values = {
                field: getattr(row, field)
                for field in (
                    "valor_string",
                    "valor_integer",
                    "valor_decimal",
                    "valor_boolean",
                    "valor_date",
                )
                if getattr(row, field) is not None
            }
            if len(previous_values) != 1:
                continue
            try:
                self._validate_default(
                    session, attribute, next(iter(previous_values.values()))
                )
            except HTTPException:
                continue
            before_value = {
                "activo": False,
                **{
                    key: str(value) if isinstance(value, Decimal) else value.isoformat()
                    if isinstance(value, date)
                    else value
                    for key, value in previous_values.items()
                },
            }
            row.activo = True
            session.add(row)
            record_domain_change(
                session,
                entity="tbl_producto_atributo_valor",
                entity_id=row.id,
                action="REACTIVATE_EAV_FOR_DEFAULT_BACKFILL",
                before=before_value,
                after={
                    "activo": True,
                    "producto_id": str(row.producto_id),
                    "atributo_id": str(row.atributo_id),
                    "preserved_value": True,
                    "mapping_id": str(categoria_atributo.id),
                },
            )

        products_without_identity = [
            product_id
            for product_id in candidate_product_ids
            if product_id not in existing_product_ids
        ]
        productos_afectados = (
            select(eligible_products.c.producto_id)
            .where(eligible_products.c.producto_id.in_(products_without_identity))
            .subquery()
        )

        valor_string_expr = literal(None, type_=String())
        valor_integer_expr = literal(None, type_=Integer())
        valor_decimal_expr = literal(None, type_=Numeric(18, 6))
        valor_boolean_expr = literal(None, type_=Boolean())
        valor_date_expr = literal(None, type_=Date())

        if tipo_normalizado in {
            TipoDato.STRING.value,
            TipoDato.SELECT.value,
            TipoDato.CATALOG.value,
        }:
            valor_string_expr = literal(valor_tipado, type_=String())
        elif tipo_normalizado == TipoDato.INTEGER.value:
            valor_integer_expr = literal(valor_tipado, type_=Integer())
        elif tipo_normalizado == TipoDato.DECIMAL.value:
            valor_decimal_expr = literal(valor_tipado, type_=Numeric(18, 6))
        elif tipo_normalizado == TipoDato.BOOLEAN.value:
            valor_boolean_expr = literal(valor_tipado, type_=Boolean())
        elif tipo_normalizado == TipoDato.DATE.value:
            valor_date_expr = literal(valor_tipado, type_=Date())

        bind = session.get_bind()
        dialect_name = bind.dialect.name if bind is not None else ""
        product_attribute_table = SQLModel.metadata.tables[
            "tbl_producto_atributo_valor"
        ]

        insert_stmt: Any
        id_expr: ColumnElement[Any]
        if dialect_name == "postgresql":
            insert_stmt = pg_insert(product_attribute_table)
            id_expr = cast(
                func.md5(
                    func.concat(
                        cast(productos_afectados.c.producto_id, String()),
                        literal(str(categoria_atributo.atributo_id)),
                    )
                ),
                PGUUID(as_uuid=True),
            )
        elif dialect_name == "sqlite":
            insert_stmt = sqlite_insert(product_attribute_table).prefix_with(
                "OR IGNORE"
            )
            id_expr = func.lower(func.hex(func.randomblob(16)))
        else:
            insert_stmt = sa_insert(product_attribute_table)
            id_expr = cast(
                func.md5(
                    func.concat(
                        cast(productos_afectados.c.producto_id, String()),
                        literal(str(categoria_atributo.atributo_id)),
                    )
                ),
                String(),
            )

        select_stmt = select(id_expr.label("id")).add_columns(
            productos_afectados.c.producto_id.label("producto_id"),
            literal(categoria_atributo.atributo_id).label("atributo_id"),
            valor_string_expr.label("valor_string"),
            valor_integer_expr.label("valor_integer"),
            valor_decimal_expr.label("valor_decimal"),
            valor_boolean_expr.label("valor_boolean"),
            valor_date_expr.label("valor_date"),
        )

        stmt = insert_stmt.from_select(
            [
                "id",
                "producto_id",
                "atributo_id",
                "valor_string",
                "valor_integer",
                "valor_decimal",
                "valor_boolean",
                "valor_date",
            ],
            select_stmt,
        )

        if dialect_name == "postgresql" and hasattr(stmt, "on_conflict_do_nothing"):
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["producto_id", "atributo_id"]
            )

        session.exec(stmt)
        session.flush()

    def required_attribute_impact(
        self,
        session: Session,
        mapping: CategoriaAtributo,
        *,
        proposed: bool = False,
        proposed_attribute: Atributo | None = None,
    ) -> tuple[dict[str, Any], list[UUID], list[UUID], dict[UUID, str]]:
        descendants = (
            select(
                col(Categoria.id).label("categoria_id"),
                col(Categoria.parent_id).label("parent_id"),
                literal(0).label("depth"),
                (literal("|") + cast(col(Categoria.id), String) + literal("|")).label(
                    "path"
                ),
            )
            .where(
                col(Categoria.id) == mapping.categoria_id,
                col(Categoria.activo).is_(True),
            )
            .cte(name="required_attribute_descendants", recursive=True)
        )
        child = aliased(Categoria, name="required_attribute_child")
        descendants = descendants.union_all(
            select(
                col(child.id),
                col(child.parent_id),
                (descendants.c.depth + 1).label("depth"),
                (
                    descendants.c.path
                    + cast(col(child.id), String)
                    + literal("|")
                ),
            )
            .select_from(descendants)
            .join(child, col(child.parent_id) == descendants.c.categoria_id)
            .where(
                col(child.activo).is_(True),
                descendants.c.path.not_like(
                    literal("%|") + cast(col(child.id), String) + literal("|%")
                ),
            )
        )
        descendant_rows = session.exec(
            select(descendants.c.categoria_id, descendants.c.depth)
        ).all()
        descendant_ids = [category_id for category_id, _ in descendant_rows]
        descendant_depths = dict(descendant_rows)
        if not descendant_ids:
            return {"mapping": str(mapping.id), "products": [], "values": []}, [], [], {}

        effective = get_effective_attributes_by_category(session, descendant_ids)
        attribute = proposed_attribute or session.get(Atributo, mapping.atributo_id)
        definition_state = (
            {
                "id": str(attribute.id),
                "codigo": attribute.codigo,
                "nombre": attribute.nombre,
                "tipo_dato": str(attribute.tipo_dato),
                "unidad_id": str(attribute.unidad_id) if attribute.unidad_id else None,
                "select_options": attribute.select_options,
                "catalog_id": str(attribute.catalog_id) if attribute.catalog_id else None,
                "allow_negative": attribute.allow_negative,
                "min_value": str(attribute.min_value) if attribute.min_value is not None else None,
                "max_value": str(attribute.max_value) if attribute.max_value is not None else None,
                "activo": attribute.activo,
            }
            if attribute is not None
            else None
        )
        effective_mapping_state = sorted(
            (
                str(category_id),
                str(item["mapping_id"]),
                bool(item["obligatorio"]),
                item["valor_default"],
                item["orden"],
            )
            for category_id, attributes in effective.items()
            for item in attributes
            if item["atributo_id"] == mapping.atributo_id
        )
        candidate_ids = list(
            session.exec(
                select(col(Producto.id))
                .where(
                    col(Producto.categoria_principal_id).in_(descendant_ids),
                    col(Producto.activo).is_(True),
                )
                .distinct()
            ).all()
        )
        if not candidate_ids:
            return {
                "mapping": {
                    "id": None if proposed else str(mapping.id),
                    "categoria_id": str(mapping.categoria_id),
                    "atributo_id": str(mapping.atributo_id),
                    "obligatorio": mapping.obligatorio,
                    "valor_default": mapping.valor_default,
                    "activo": mapping.activo,
                },
                "definition": definition_state,
                "effective_mappings": effective_mapping_state,
                "products": [],
                "values": [],
            }, [], [], {}

        category_rows = session.exec(
            select(
                col(Producto.id),
                col(Producto.categoria_principal_id),
            )
            .join(Categoria, col(Categoria.id) == col(Producto.categoria_principal_id))
            .where(
                col(Producto.id).in_(candidate_ids),
                col(Producto.activo).is_(True),
                col(Categoria.activo).is_(True),
            )
        ).all()

        categories_by_product: dict[UUID, set[UUID]] = defaultdict(set)
        for product_id, category_id in category_rows:
            if category_id is None:
                continue
            categories_by_product[product_id].add(category_id)
        effective_product_ids: list[UUID] = []
        for product_id, category_ids in categories_by_product.items():
            scope_id = resolve_unambiguous_category_scope(
                session, list(category_ids)
            )
            if scope_id is None:
                continue
            effective_mapping = next(
                (
                    item
                    for item in effective.get(scope_id, [])
                    if item["atributo_id"] == mapping.atributo_id
                ),
                None,
            )
            if not proposed and effective_mapping is not None and str(
                effective_mapping["mapping_id"]
            ) == str(mapping.id):
                effective_product_ids.append(product_id)
            elif proposed:
                target_depth = descendant_depths.get(scope_id)
                current_depth = (
                    effective_mapping["profundidad"]
                    if effective_mapping is not None
                    else None
                )
                if target_depth is not None and (
                    current_depth is None or target_depth < current_depth
                ):
                    effective_product_ids.append(product_id)

        products = {
            product.id: product.nombre
            for product in session.exec(
                select(Producto).where(col(Producto.id).in_(effective_product_ids))
            ).all()
        } if effective_product_ids else {}
        value_rows = session.exec(
            select(ProductoAtributoValor)
            .where(
                col(ProductoAtributoValor.producto_id).in_(effective_product_ids),
                col(ProductoAtributoValor.atributo_id) == mapping.atributo_id,
            )
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        ).all() if effective_product_ids else []
        values_by_product = {row.producto_id: row for row in value_rows}
        missing_ids: list[UUID] = []
        for product_id in effective_product_ids:
            value_row = values_by_product.get(product_id)
            valid = value_row is not None and value_row.activo
            if valid:
                typed_values = [
                    getattr(value_row, field)
                    for field in (
                        "valor_string",
                        "valor_integer",
                        "valor_decimal",
                        "valor_boolean",
                        "valor_date",
                    )
                    if getattr(value_row, field) is not None
                ]
                try:
                    if len(typed_values) != 1:
                        raise self._invalid_default()
                    self._validate_default(session, attribute, typed_values[0])
                except HTTPException:
                    valid = False
            if not valid:
                missing_ids.append(product_id)

        state = {
            "mapping": {
                "id": None if proposed else str(mapping.id),
                "categoria_id": str(mapping.categoria_id),
                "atributo_id": str(mapping.atributo_id),
                "obligatorio": mapping.obligatorio,
                "valor_default": mapping.valor_default,
                "activo": mapping.activo,
            },
            "definition": definition_state,
            "effective_mappings": effective_mapping_state,
            "products": sorted(str(product_id) for product_id in effective_product_ids),
            "product_categories": sorted(
                (str(product_id), str(category_id)) for product_id, category_id in category_rows
            ),
            "values": sorted(
                (
                    str(row.id),
                    str(row.producto_id),
                    row.activo,
                    str(row.valor_string) if row.valor_string is not None else None,
                    str(row.valor_integer) if row.valor_integer is not None else None,
                    str(row.valor_decimal) if row.valor_decimal is not None else None,
                    str(row.valor_boolean) if row.valor_boolean is not None else None,
                    str(row.valor_date) if row.valor_date is not None else None,
                )
                for row in value_rows
            ),
        }
        return state, effective_product_ids, missing_ids, products

    @staticmethod
    def _raise_required_attribute_missing(
        missing_ids: list[UUID], product_names: dict[UUID, str]
    ) -> None:
        if not missing_ids:
            return
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PRODUCT_REQUIRED_ATTRIBUTES_MISSING",
                "message": "La asignación dejaría productos activos sin un valor válido para un atributo obligatorio.",
                "conteos": {"productos": len(missing_ids)},
                "affected_ids": [str(product_id) for product_id in missing_ids],
                "affected_names": [product_names.get(product_id, "Producto") for product_id in missing_ids],
                "acciones_permitidas": ["proporcionar_valores", "aplicar_default", "cancelar"],
            },
        )
    def list_paginated(
        self,
        session: Session,
        skip: int = 0,
        limit: int = 50,
        categoria_id: Optional[UUID] = None,
    ) -> list[CategoriaAtributo]:
        query = select(CategoriaAtributo).where(col(CategoriaAtributo.activo).is_(True))
        if categoria_id:
            query = query.where(CategoriaAtributo.categoria_id == categoria_id)
        query = query.offset(skip).limit(limit)
        return list(session.exec(query))

    def get(self, session: Session, id: UUID) -> Optional[CategoriaAtributo]:
        return session.get(CategoriaAtributo, id)

    def create(
        self,
        session: Session,
        dto: CategoriaAtributoCreate,
        usuario_auditoria: Optional[str] = None,
        *,
        commit: bool = True,
    ) -> CategoriaAtributo:
        if isinstance(session, Session):
            from osiris.modules.inventario.categoria.service import CategoriaService

            CategoriaService.acquire_hierarchy_mutation_lock(session)
        self._validar_asignacion_historica(session, dto.categoria_id, dto.atributo_id)
        self._validar_nombre_unico_global(session, dto.categoria_id, dto.atributo_id)
        atributo_master = (
            session.get(Atributo, dto.atributo_id)
            if dto.valor_default is not None or dto.aplicar_default_a_existentes
            else None
        )
        valor_default = (
            self._validate_default(session, atributo_master, dto.valor_default)
            if dto.valor_default is not None
            else None
        )
        if dto.aplicar_default_a_existentes and valor_default is None:
            raise self._invalid_default()

        entity = CategoriaAtributo(
            categoria_id=dto.categoria_id,
            atributo_id=dto.atributo_id,
            orden=dto.orden,
            obligatorio=dto.obligatorio,
            valor_default=valor_default,
            usuario_auditoria=usuario_auditoria or "api",
            activo=True,
        )
        try:
            session.add(entity)
            if dto.aplicar_default_a_existentes:
                self._ejecutar_backfill_atributo(
                    session,
                    entity,
                    getattr(atributo_master, "tipo_dato", None),
                )
            if entity.obligatorio is True and isinstance(session, Session):
                session.flush()
                _, _, missing_ids, product_names = self.required_attribute_impact(
                    session, entity
                )
                if missing_ids:
                    if commit:
                        session.rollback()
                    self._raise_required_attribute_missing(missing_ids, product_names)
            if isinstance(session, Session):
                record_domain_change(
                    session,
                    entity="tbl_categoria_atributo",
                    entity_id=entity.id,
                    action="CREATE_CATEGORY_ATTRIBUTE",
                    before={},
                    after={
                        "categoria_id": str(entity.categoria_id),
                        "atributo_id": str(entity.atributo_id),
                        "obligatorio": entity.obligatorio,
                        "valor_default": entity.valor_default,
                    },
                )
            if commit:
                session.commit()
                session.refresh(entity)
            else:
                session.flush()
        except IntegrityError as error:
            if commit:
                session.rollback()
            self._raise_integrity(error)
        except Exception:
            if commit and isinstance(session, Session) and session.in_transaction():
                session.rollback()
            raise
        return entity

    def assign_existing(
        self,
        session: Session,
        categoria_id: UUID,
        data: dict[str, Any],
        usuario_auditoria: Optional[str] = None,
        *,
        commit: bool = True,
    ) -> CategoriaAtributo:
        from osiris.modules.inventario.categoria.service import CategoriaService

        categoria_id = UUID(str(categoria_id))
        values = data.copy()
        atributo_id = UUID(str(values.pop("atributo_id")))
        apply_default = values.pop("aplicar_default_a_existentes", False) is True
        values.pop("usuario_auditoria", None)
        try:
            CategoriaService.acquire_hierarchy_mutation_lock(session)
            self._validar_nombre_unico_global(session, categoria_id, atributo_id)
            existing = session.exec(
                select(CategoriaAtributo)
                .where(
                    col(CategoriaAtributo.categoria_id) == categoria_id,
                    col(CategoriaAtributo.atributo_id) == atributo_id,
                )
                .with_for_update()
                .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
            ).first()
            if existing is not None and existing.activo:
                raise self._already_assigned()

            was_inactive = existing is not None
            mapping = existing or CategoriaAtributo(
                categoria_id=categoria_id,
                atributo_id=atributo_id,
                orden=None,
                obligatorio=False,
                valor_default=None,
            )
            before = (
                {
                    "activo": mapping.activo,
                    "orden": mapping.orden,
                    "obligatorio": mapping.obligatorio,
                    "valor_default": mapping.valor_default,
                }
                if was_inactive
                else {}
            )
            for field in ("orden", "obligatorio", "valor_default"):
                if field in values:
                    value = values[field]
                    if field == "valor_default" and value is not None:
                        attribute = session.get(Atributo, atributo_id)
                        value = self._validate_default(session, attribute, value)
                    setattr(mapping, field, value)
            if apply_default and self._is_empty_default(mapping.valor_default):
                raise self._invalid_default()
            mapping.activo = True
            if usuario_auditoria:
                mapping.usuario_auditoria = usuario_auditoria
            session.add(mapping)
            if apply_default:
                attribute = session.get(Atributo, atributo_id)
                self._ejecutar_backfill_atributo(
                    session, mapping, getattr(attribute, "tipo_dato", None)
                )
            if mapping.obligatorio is True and isinstance(session, Session):
                session.flush()
                _, _, missing_ids, product_names = self.required_attribute_impact(
                    session, mapping
                )
                self._raise_required_attribute_missing(missing_ids, product_names)
            record_domain_change(
                session,
                entity="tbl_categoria_atributo",
                entity_id=mapping.id,
                action=(
                    "REACTIVATE_CATEGORY_ATTRIBUTE"
                    if was_inactive
                    else "ASSIGN_CATEGORY_ATTRIBUTE"
                ),
                before=before,
                after={
                    "categoria_id": str(categoria_id),
                    "atributo_id": str(atributo_id),
                    "activo": True,
                    "orden": mapping.orden,
                    "obligatorio": mapping.obligatorio,
                    "valor_default": mapping.valor_default,
                    "aplicar_default_a_existentes": apply_default,
                },
            )
            if commit:
                session.commit()
                session.refresh(mapping)
            else:
                session.flush()
            return mapping
        except IntegrityError as error:
            if commit:
                session.rollback()
            self._raise_integrity(error)
            raise
        except Exception:
            if commit and session.in_transaction():
                session.rollback()
            raise

    def update(
        self,
        session: Session,
        id: UUID,
        dto: CategoriaAtributoUpdate,
        usuario_auditoria: Optional[str] = None,
    ) -> Optional[CategoriaAtributo]:
        if isinstance(session, Session):
            from osiris.modules.inventario.categoria.service import CategoriaService

            CategoriaService.acquire_hierarchy_mutation_lock(session)
        entity = session.get(CategoriaAtributo, id)
        if not entity:
            return None

        before_mapping = {
            "categoria_id": str(entity.categoria_id),
            "atributo_id": str(entity.atributo_id),
            "orden": entity.orden,
            "obligatorio": entity.obligatorio,
            "valor_default": entity.valor_default,
        }
        atributo_master: Optional[Atributo] = None
        fields_set = dto.model_fields_set
        next_default = entity.valor_default
        if "valor_default" in fields_set:
            if dto.valor_default is None:
                next_default = None
            else:
                atributo_master = session.get(Atributo, entity.atributo_id)
                next_default = self._validate_default(
                    session, atributo_master, dto.valor_default
                )
        if dto.aplicar_default_a_existentes and self._is_empty_default(next_default):
            raise self._invalid_default()

        if "orden" in fields_set:
            entity.orden = dto.orden
        if dto.obligatorio is not None:
            entity.obligatorio = dto.obligatorio
        if "valor_default" in fields_set:
            entity.valor_default = next_default

        entity.usuario_auditoria = usuario_auditoria or entity.usuario_auditoria
        session.add(entity)
        if dto.aplicar_default_a_existentes:
            if atributo_master is None:
                atributo_master = session.get(Atributo, entity.atributo_id)
            self._ejecutar_backfill_atributo(
                session,
                entity,
                getattr(atributo_master, "tipo_dato", None),
            )
        if entity.obligatorio is True and isinstance(session, Session):
            session.flush()
            _, _, missing_ids, product_names = self.required_attribute_impact(
                session, entity
            )
            if missing_ids:
                session.rollback()
                self._raise_required_attribute_missing(missing_ids, product_names)
        if isinstance(session, Session):
            record_domain_change(
                session,
                entity="tbl_categoria_atributo",
                entity_id=entity.id,
                action="UPDATE_CATEGORY_ATTRIBUTE",
                before=before_mapping,
                after={
                    "categoria_id": str(entity.categoria_id),
                    "atributo_id": str(entity.atributo_id),
                    "orden": entity.orden,
                    "obligatorio": entity.obligatorio,
                    "valor_default": entity.valor_default,
                },
            )
        session.commit()
        session.refresh(entity)
        return entity

    def local_removal_impact(
        self, session: Session, mapping: CategoriaAtributo
    ) -> tuple[
        dict[str, Any],
        list[UUID],
        list[UUID],
        list[UUID],
        dict[UUID, str],
        list[UUID],
        list[ProductoAtributoRemapeo],
    ]:
        state, affected_ids, _, names = self.required_attribute_impact(
            session, mapping
        )
        if not affected_ids:
            return state, [], [], [], names, [], []
        pending_remaps = list(
            session.exec(
                select(ProductoAtributoRemapeo)
                .where(
                    col(ProductoAtributoRemapeo.producto_id).in_(affected_ids),
                    col(ProductoAtributoRemapeo.atributo_id) == mapping.atributo_id,
                    col(ProductoAtributoRemapeo.activo).is_(True),
                )
                .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
            ).all()
        )

        category_rows = session.exec(
            select(
                col(Producto.id),
                col(Producto.categoria_principal_id),
            )
            .join(Categoria, col(Categoria.id) == col(Producto.categoria_principal_id))
            .where(
                col(Producto.id).in_(affected_ids),
                col(Producto.activo).is_(True),
                col(Categoria.activo).is_(True),
            )
        ).all()
        categories_by_product: dict[UUID, set[UUID]] = defaultdict(set)
        for product_id, category_id in category_rows:
            if category_id is None:
                continue
            categories_by_product[product_id].add(category_id)
        category_scopes = {
            product_id: resolve_unambiguous_category_scope(
                session, list(category_ids)
            )
            for product_id, category_ids in categories_by_product.items()
        }
        scope_ids = list({scope_id for scope_id in category_scopes.values() if scope_id})
        after_by_category = get_effective_attributes_by_category(
            session, scope_ids, excluded_mapping_ids={mapping.id}
        )
        values = session.exec(
            select(ProductoAtributoValor)
            .where(
                col(ProductoAtributoValor.producto_id).in_(affected_ids),
                col(ProductoAtributoValor.atributo_id) == mapping.atributo_id,
            )
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        ).all()
        values_by_product = {row.producto_id: row for row in values}
        remove_value_ids: list[UUID] = []
        retained_product_ids: list[UUID] = []
        retained_value_ids: list[UUID] = []
        for product_id, scope_id in category_scopes.items():
            if scope_id is None:
                continue
            applicable = any(
                item["atributo_id"] == mapping.atributo_id
                for item in after_by_category.get(scope_id, [])
            )
            value = values_by_product.get(product_id)
            if applicable:
                retained_product_ids.append(product_id)
                if value is not None and value.activo:
                    retained_value_ids.append(value.id)
            elif value is not None and value.activo:
                remove_value_ids.append(value.id)

        active_attribute_ids = {
            item["atributo_id"]
            for attributes in after_by_category.values()
            for item in attributes
            if item["obligatorio"]
        }
        definitions = {
            attribute.id: attribute
            for attribute in session.exec(
                select(Atributo).where(col(Atributo.id).in_(active_attribute_ids))
            ).all()
        } if active_attribute_ids else {}
        all_values = session.exec(
            select(ProductoAtributoValor)
            .where(
                col(ProductoAtributoValor.producto_id).in_(affected_ids),
                col(ProductoAtributoValor.atributo_id).in_(active_attribute_ids),
                col(ProductoAtributoValor.activo).is_(True),
            )
        ).all() if active_attribute_ids else []
        values_by_key = {
            (row.producto_id, row.atributo_id): row for row in all_values
        }
        missing_after: set[UUID] = set()
        for product_id, scope_id in category_scopes.items():
            if scope_id is None:
                continue
            for item in after_by_category.get(scope_id, []):
                if not item["obligatorio"]:
                    continue
                value = values_by_key.get((product_id, item["atributo_id"]))
                attribute = definitions.get(item["atributo_id"])
                valid = value is not None
                if valid:
                    typed_values = [
                        getattr(value, field)
                        for field in (
                            "valor_string",
                            "valor_integer",
                            "valor_decimal",
                            "valor_boolean",
                            "valor_date",
                        )
                        if getattr(value, field) is not None
                    ]
                    try:
                        if len(typed_values) != 1:
                            raise self._invalid_default()
                        self._validate_default(session, attribute, typed_values[0])
                    except HTTPException:
                        valid = False
                if not valid:
                    missing_after.add(product_id)

        state = {
            **state,
            "effective_after": sorted(
                (
                    str(scope_id),
                    str(item["mapping_id"]),
                    str(item["atributo_id"]),
                    item["obligatorio"],
                    item["valor_default"],
                )
                for scope_id, attributes in after_by_category.items()
                for item in attributes
            ),
            "remove_value_ids": sorted(str(value_id) for value_id in remove_value_ids),
            "retained_value_ids": sorted(str(value_id) for value_id in retained_value_ids),
            "retained_product_ids": sorted(
                str(product_id) for product_id in retained_product_ids
            ),
            "missing_after": sorted(str(product_id) for product_id in missing_after),
            "pending_remaps": sorted(
                (
                    str(remap.id),
                    str(remap.producto_id),
                    remap.tipo_anterior,
                    remap.tipo_nuevo,
                    remap.motivo,
                )
                for remap in pending_remaps
            ),
        }
        return (
            state,
            affected_ids,
            remove_value_ids,
            sorted(missing_after, key=str),
            names,
            retained_value_ids,
            pending_remaps,
        )

    def remove_local_assignment(
        self,
        session: Session,
        mapping: CategoriaAtributo,
        *,
        usuario_auditoria: str,
        commit: bool = True,
    ) -> list[UUID]:
        try:
            from osiris.modules.inventario.categoria.service import CategoriaService

            CategoriaService.acquire_hierarchy_mutation_lock(session)
            if not mapping.activo:
                return []
            _, _, remove_value_ids, missing_after, names, _, pending_remaps = (
                self.local_removal_impact(session, mapping)
            )
            if pending_remaps:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "ATTRIBUTE_HAS_PENDING_REMAPS",
                        "message": "Resuelve los remapeos antes de quitar esta asignación.",
                        "conteos": {"remapeos_pendientes": len(pending_remaps)},
                        "affected_ids": [str(remap.id) for remap in pending_remaps],
                        "acciones_permitidas": ["resolver_remapeos", "cancelar"],
                    },
                )
            self._raise_required_attribute_missing(missing_after, names)
            before_mapping = {
                "categoria_id": str(mapping.categoria_id),
                "atributo_id": str(mapping.atributo_id),
                "orden": mapping.orden,
                "obligatorio": mapping.obligatorio,
                "valor_default": mapping.valor_default,
                "activo": mapping.activo,
            }
            mapping.activo = False
            mapping.usuario_auditoria = usuario_auditoria
            session.add(mapping)
            if remove_value_ids:
                values = session.exec(
                    select(ProductoAtributoValor)
                    .where(col(ProductoAtributoValor.id).in_(remove_value_ids))
                    .with_for_update()
                ).all()
                for value in values:
                    before_value = {
                        field: getattr(value, field).isoformat()
                        if isinstance(getattr(value, field), date)
                        else str(getattr(value, field))
                        if isinstance(getattr(value, field), Decimal)
                        else getattr(value, field)
                        for field in (
                            "valor_string",
                            "valor_integer",
                            "valor_decimal",
                            "valor_boolean",
                            "valor_date",
                        )
                    }
                    value.activo = False
                    session.add(value)
                    record_domain_change(
                        session,
                        entity="tbl_producto_atributo_valor",
                        entity_id=value.id,
                        action="REMOVE_CATEGORY_ATTRIBUTE_VALUE",
                        before=before_value,
                        after={
                            "activo": False,
                            "mapping_id": str(mapping.id),
                            "producto_id": str(value.producto_id),
                            "atributo_id": str(value.atributo_id),
                        },
                    )
            record_domain_change(
                session,
                entity="tbl_categoria_atributo",
                entity_id=mapping.id,
                action="REMOVE_CATEGORY_ATTRIBUTE",
                before=before_mapping,
                after={
                    "activo": False,
                    "valores_desactivados": len(remove_value_ids),
                },
            )
            if commit:
                session.commit()
            else:
                session.flush()
            return remove_value_ids
        except Exception:
            if commit and session.in_transaction():
                session.rollback()
            raise

    def delete(
        self, session: Session, id: UUID, usuario_auditoria: Optional[str] = None
    ) -> bool:
        entity = session.get(CategoriaAtributo, id)
        if not entity:
            return False
        before_mapping = {
            "categoria_id": str(entity.categoria_id),
            "atributo_id": str(entity.atributo_id),
            "obligatorio": entity.obligatorio,
            "valor_default": entity.valor_default,
            "activo": entity.activo,
        }
        entity.activo = False
        entity.usuario_auditoria = usuario_auditoria or entity.usuario_auditoria
        session.add(entity)
        if isinstance(session, Session):
            record_domain_change(
                session,
                entity="tbl_categoria_atributo",
                entity_id=entity.id,
                action="DELETE_CATEGORY_ATTRIBUTE",
                before=before_mapping,
                after={"activo": False},
            )
        session.commit()
        return True
