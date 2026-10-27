from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from osiris.utils.attribute_code import generate_attribute_code


REQUIRED_COLUMNS = {
    "tbl_categoria": {"id", "nombre", "parent_id", "activo", "es_padre", "is_default"},
    "tbl_atributo": {"id", "nombre", "tipo_dato", "activo"},
    "tbl_categoria_atributo": {
        "id",
        "categoria_id",
        "atributo_id",
        "obligatorio",
        "valor_default",
        "activo",
    },
    "tbl_producto": {"id", "nombre", "activo"},
    "tbl_producto_categoria": {"id", "producto_id", "categoria_id"},
    "tbl_producto_atributo_valor": {
        "id",
        "producto_id",
        "atributo_id",
        "activo",
        "valor_string",
        "valor_integer",
        "valor_decimal",
        "valor_boolean",
        "valor_date",
    },
}


def _identifier(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return str(UUID(str(value)))
    except ValueError:
        return str(value)


def _normalized(value: Any) -> str:
    return str(value or "").strip().lower()


def _read_rows(connection: Connection, table: sa.Table) -> list[dict[str, Any]]:
    return [
        {
            key: _identifier(value) if key == "id" or key.endswith("_id") else value
            for key, value in row.items()
        }
        for row in connection.execute(sa.select(table).order_by(table.c.id)).mappings()
    ]


def audit_catalog(
    connection: Connection,
    *,
    unit_candidates: Mapping[str, str] | None = None,
    product_cutover: bool = False,
) -> dict[str, Any]:
    inspector = sa.inspect(connection)
    available = set(inspector.get_table_names())
    missing: dict[str, list[str]] = {}
    tables: dict[str, sa.Table] = {}
    metadata = sa.MetaData()
    for name, columns in REQUIRED_COLUMNS.items():
        if name not in available:
            missing[name] = sorted(columns)
            continue
        table = sa.Table(name, metadata, autoload_with=connection)
        absent = columns - set(table.c.keys())
        if absent:
            missing[name] = sorted(absent)
        tables[name] = table

    conflicts: list[dict[str, Any]] = []
    has_primary_category_column = (
        "tbl_producto" in tables and "categoria_principal_id" in tables["tbl_producto"].c
    )
    report: dict[str, Any] = {
        "version": 1,
        "alcance": "producto_cutover" if product_cutover else "catalogo_global",
        "fuente_categoria_principal": (
            "tbl_producto.categoria_principal_id"
            if has_primary_category_column
            else "tbl_producto_categoria_legacy"
        ),
        "apto_para_migrar": False,
        "total_conflictos": 0,
        "conteos": {},
        "conflictos": conflicts,
        "candidatos_backfill_categoria": [],
        "candidatos_anotacion_unidad": [],
        "advertencias": [],
    }
    if missing:
        conflicts.append(
            {
                "code": "CATALOG_SCHEMA_INCOMPLETE",
                "message": "Faltan tablas o columnas requeridas para auditar el catalogo.",
                "ids": [],
                "faltantes": missing,
            }
        )
        report["total_conflictos"] = 1
        return report

    rows = {name: _read_rows(connection, table) for name, table in tables.items()}
    for name in (
        "tbl_producto_atributo_remapeo",
        "tbl_atributo_cambio",
        "tbl_catalogo_valor",
        "tbl_unidad",
    ):
        if name in available:
            rows[name] = _read_rows(connection, sa.Table(name, metadata, autoload_with=connection))
    report["conteos"] = {name: len(records) for name, records in rows.items()}
    categories = {row["id"]: row for row in rows["tbl_categoria"]}

    def category_path(category_id: str | None) -> str:
        parts: list[str] = []
        visited: set[str] = set()
        current_id = category_id
        while current_id is not None and current_id in categories:
            if current_id in visited:
                parts.append("[ciclo]")
                break
            visited.add(current_id)
            category = categories[current_id]
            parts.append(str(category["nombre"]))
            current_id = category["parent_id"]
        return " > ".join(reversed(parts))

    def issue(code: str, message: str, records: list[dict[str, Any]], **details: Any) -> None:
        conflicts.append(
            {
                "code": code,
                "message": message,
                "ids": sorted(str(row["id"]) for row in records),
                "registros": sorted(
                    [
                        {
                            "id": str(row["id"]),
                            "nombre": row.get("nombre"),
                            "activo": row.get("activo"),
                        }
                        for row in records
                    ],
                    key=lambda record: record["id"],
                ),
                **details,
            }
        )

    sibling_groups: dict[tuple[str | None, str], list[dict[str, Any]]] = defaultdict(list)
    active_children: dict[str, list[str]] = defaultdict(list)
    for category in categories.values():
        sibling_groups[(category["parent_id"], _normalized(category["nombre"]))].append(category)
        if category["activo"] and category["parent_id"] is not None:
            active_children[category["parent_id"]].append(category["id"])
        parent = categories.get(category["parent_id"])
        if category["parent_id"] is not None and (
            parent is None or (category["activo"] and not parent["activo"])
        ):
            issue(
                "CATEGORY_PARENT_INVALID",
                "La categoria tiene un padre inexistente o inactivo.",
                [category],
                parent_id=category["parent_id"],
            )

    for (parent_id, normalized_name), records in sibling_groups.items():
        if len(records) > 1:
            issue(
                "CATEGORY_DUPLICATE_NAME",
                "Existen categorias hermanas equivalentes, incluyendo historial inactivo.",
                records,
                parent_id=parent_id,
                ruta_padre=category_path(parent_id),
                nombre_normalizado=normalized_name,
            )

    processed: set[str] = set()
    for category_id in categories:
        chain: list[str] = []
        positions: dict[str, int] = {}
        current_id: str | None = category_id
        while current_id is not None and current_id in categories and current_id not in processed:
            if current_id in positions:
                cycle = chain[positions[current_id] :]
                issue(
                    "CATEGORY_CYCLE",
                    "Existe un ciclo en la jerarquia.",
                    [categories[member] for member in cycle],
                )
                break
            positions[current_id] = len(chain)
            chain.append(current_id)
            current_id = categories[current_id]["parent_id"]
        processed.update(chain)

    for category in categories.values():
        expected = bool(active_children[category["id"]])
        if bool(category["es_padre"]) != expected:
            issue(
                "CATEGORY_PARENT_FLAG_MISMATCH",
                "es_padre no coincide con los hijos activos.",
                [category],
                ruta=category_path(category["id"]),
                tiene_hijos=expected,
            )

    attributes = rows["tbl_atributo"]
    for field, active_only, code in (
        ("nombre", True, "ATTRIBUTE_DUPLICATE_NAME"),
        ("codigo", False, "ATTRIBUTE_DUPLICATE_CODE"),
    ):
        if field not in tables["tbl_atributo"].c:
            report["advertencias"].append(
                {
                    "code": "ATTRIBUTE_CODE_NOT_DEPLOYED",
                    "message": "La columna codigo aun no existe; se validan codigos previstos sin persistirlos.",
                }
            )
            generated_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for attribute in attributes:
                try:
                    generated_groups[generate_attribute_code(attribute["nombre"])].append(attribute)
                except ValueError:
                    issue("ATTRIBUTE_CODE_TOO_LONG", "El codigo previsto supera el limite permitido.", [attribute])
            for generated_code, generated_records in generated_groups.items():
                if len(generated_records) > 1:
                    issue("ATTRIBUTE_DUPLICATE_CODE", "Varios atributos activos o historicos generarian el mismo codigo.", generated_records, clave_normalizada=generated_code, codigo_previsto=True)
            continue
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for attribute in attributes:
            if active_only and not attribute["activo"]:
                continue
            normalized_name = _normalized(attribute[field])
            if normalized_name:
                groups[normalized_name].append(attribute)
        for normalized_name, records in groups.items():
            if len(records) > 1:
                issue(
                    code,
                    "Existen atributos con identidad normalizada duplicada.",
                    records,
                    campo=field,
                    clave_normalizada=normalized_name,
                )

    mapping_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for mapping in rows["tbl_categoria_atributo"]:
        mapping_groups[(mapping["categoria_id"], mapping["atributo_id"])].append(mapping)
    for (category_id, attribute_id), records in mapping_groups.items():
        if len(records) > 1:
            issue(
                "CATEGORY_ATTRIBUTE_DUPLICATE",
                "Existe mas de una identidad historica para la asignacion.",
                records,
                categoria_id=category_id,
                atributo_id=attribute_id,
                ruta=category_path(category_id),
            )

    attribute_by_id = {attribute["id"]: attribute for attribute in attributes}
    products = {product["id"]: product for product in rows["tbl_producto"]}
    classifications: dict[str, list[dict[str, Any]]] = defaultdict(list)
    values_by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    mappings_by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    pending_remaps = {
        (remap["producto_id"], remap["atributo_id"])
        for remap in rows.get("tbl_producto_atributo_remapeo", [])
        if remap["activo"]
    }
    for classification in rows["tbl_producto_categoria"]:
        if classification.get("activo", True):
            classifications[classification["producto_id"]].append(classification)
    for value in rows["tbl_producto_atributo_valor"]:
        if value["activo"]:
            values_by_key[(value["producto_id"], value["atributo_id"])].append(value)
    for mapping in rows["tbl_categoria_atributo"]:
        if mapping["activo"]:
            mappings_by_category[mapping["categoria_id"]].append(mapping)

    for category in categories.values():
        if category["is_default"] and (
            category["parent_id"] is None or active_children[category["id"]]
        ):
            issue(
                "CATEGORY_DEFAULT_INVALID",
                "El bucket temporal debe ser una hoja con categoria de origen.",
                [category],
            )

    typed_columns = {
        "string": "valor_string",
        "select": "valor_string",
        "catalog": "valor_string",
        "integer": "valor_integer",
        "decimal": "valor_decimal",
        "boolean": "valor_boolean",
        "date": "valor_date",
    }

    def valid_value(attribute: dict[str, Any], value: dict[str, Any]) -> bool:
        kind = _normalized(attribute["tipo_dato"])
        column = typed_columns.get(kind)
        if column is None or value.get(column) is None:
            return False
        if sum(value.get(field) is not None for field in set(typed_columns.values())) != 1:
            return False
        raw = value[column]
        if kind in {"string", "select", "catalog"} and not str(raw).strip():
            return False
        if kind in {"integer", "decimal"}:
            try:
                numeric = Decimal(str(raw))
                if not numeric.is_finite() or (
                    kind == "integer" and numeric != numeric.to_integral_value()
                ):
                    return False
                if not attribute.get("allow_negative", False) and numeric < 0:
                    return False
                if attribute.get("min_value") is not None and numeric < Decimal(
                    str(attribute["min_value"])
                ):
                    return False
                if attribute.get("max_value") is not None and numeric > Decimal(
                    str(attribute["max_value"])
                ):
                    return False
            except (InvalidOperation, ValueError):
                return False
        if kind == "select":
            options = attribute.get("select_options") or []
            return any(str(option).casefold() == str(raw).casefold() for option in options)
        if kind == "catalog":
            return any(
                option.get("catalogo_id") == attribute.get("catalog_id")
                and option.get("activo")
                and str(option.get("valor")).casefold() == str(raw).casefold()
                for option in rows.get("tbl_catalogo_valor", [])
            )
        return True

    for product in products.values():
        candidates = classifications[product["id"]]
        primary_category_id = product.get("categoria_principal_id")
        bridge_category_ids = [candidate["categoria_id"] for candidate in candidates]
        if primary_category_id is not None:
            if len(bridge_category_ids) != 1 or bridge_category_ids[0] != primary_category_id:
                issue(
                    "PRODUCT_PRIMARY_CATEGORY_CONFLICT",
                    "La categoria principal directa no coincide con la proyeccion legacy.",
                    [product],
                    categoria_principal_id=primary_category_id,
                    categorias_bridge=[
                        {"id": category_id, "ruta": category_path(category_id)}
                        for category_id in bridge_category_ids
                    ],
                )
            category_id = primary_category_id
        else:
            if len(candidates) != 1:
                issue(
                    "PRODUCT_CATEGORY_REQUIRED" if not candidates else "PRODUCT_CATEGORY_AMBIGUOUS",
                    "El producto activo necesita una clasificacion principal inequivoca.",
                    [product],
                    categorias_candidatas=[
                        {
                            "id": candidate["categoria_id"],
                            "ruta": category_path(candidate["categoria_id"]),
                        }
                        for candidate in candidates
                    ],
                )
                continue
            category_id = candidates[0]["categoria_id"]
        product_category = categories.get(category_id)
        if product_category is None or not product_category["activo"]:
            issue(
                "PRODUCT_CATEGORY_INVALID",
                "La categoria del producto no existe o esta inactiva.",
                [product],
                categoria_id=category_id,
            )
            continue
        if active_children[product_category["id"]]:
            issue(
                "PRODUCT_CATEGORY_NOT_LEAF",
                "El producto esta clasificado en una categoria no hoja.",
                [product],
                categoria_id=product_category["id"],
                ruta=category_path(product_category["id"]),
            )
            continue
        if product_category["is_default"]:
            parent = categories.get(product_category["parent_id"])
            if parent is None or not parent["activo"] or parent["is_default"]:
                issue(
                    "PRODUCT_CATEGORY_DEFAULT_INVALID",
                    "El bucket temporal no tiene un origen B3 estructuralmente valido.",
                    [product],
                    categoria_id=product_category["id"],
                )
                continue
            if product_cutover and product["activo"]:
                issue(
                    "PRODUCT_CATEGORY_TEMPORARY",
                    "El producto sigue en una categoria temporal B3 y requiere recategorizacion antes del cutover.",
                    [product],
                    categoria_id=product_category["id"],
                    ruta=category_path(product_category["id"]),
                )

        effective: dict[str, dict[str, Any]] = {}
        visited: set[str] = set()
        current_category_id: str | None = product_category["id"]
        valid_ancestry = True
        while current_category_id is not None:
            current_category = categories.get(current_category_id)
            if (
                current_category is None
                or current_category_id in visited
                or not current_category["activo"]
            ):
                valid_ancestry = False
                break
            visited.add(current_category_id)
            for mapping in mappings_by_category[current_category_id]:
                mapped_attribute = attribute_by_id.get(mapping["atributo_id"])
                if mapped_attribute is not None and mapped_attribute["activo"]:
                    effective.setdefault(mapping["atributo_id"], mapping)
            parent_id = current_category["parent_id"]
            if parent_id is not None and parent_id not in categories:
                valid_ancestry = False
                break
            current_category_id = parent_id
        if not valid_ancestry:
            issue(
                "PRODUCT_CATEGORY_ANCESTRY_INVALID",
                "No es posible resolver la herencia de forma segura.",
                [product],
                categoria_id=product_category["id"],
            )
            continue

        if primary_category_id is None and not product_category["is_default"]:
            report["candidatos_backfill_categoria"].append(
                {
                    "producto_id": product["id"],
                    "producto_nombre": product["nombre"],
                    "categoria_id": product_category["id"],
                    "ruta": category_path(product_category["id"]),
                }
            )

        if not product["activo"]:
            continue

        effective_attribute_ids = set(effective)
        for (value_product_id, attribute_id), active_values in values_by_key.items():
            if value_product_id != product["id"]:
                continue
            attribute_record = attribute_by_id.get(attribute_id)
            value_ids = sorted(value["id"] for value in active_values)
            if (
                attribute_record is None
                or not attribute_record["activo"]
                or attribute_id not in effective_attribute_ids
            ):
                issue(
                    "PRODUCT_ATTRIBUTE_NOT_APPLICABLE",
                    "El producto tiene un valor activo para un atributo fuera de su esquema efectivo.",
                    [product],
                    categoria_id=product_category["id"],
                    ruta=category_path(product_category["id"]),
                    atributo_id=attribute_id,
                    valor_ids=value_ids,
                )
                continue
            if (product["id"], attribute_id) in pending_remaps:
                issue(
                    "PRODUCT_ATTRIBUTE_REMAP_PENDING",
                    "El producto tiene un remapeo pendiente para un atributo efectivo.",
                    [product],
                    categoria_id=product_category["id"],
                    atributo_id=attribute_id,
                    valor_ids=value_ids,
                )
            if len(active_values) > 1:
                issue(
                    "PRODUCT_ATTRIBUTE_VALUE_DUPLICATE",
                    "El producto tiene mas de un valor activo para el mismo atributo.",
                    [product],
                    categoria_id=product_category["id"],
                    atributo_id=attribute_id,
                    valor_ids=value_ids,
                )
            for active_value in active_values:
                if not valid_value(attribute_record, active_value):
                    issue(
                        "PRODUCT_ATTRIBUTE_VALUE_INVALID",
                        "El valor EAV activo no cumple el tipo o las restricciones del atributo.",
                        [product],
                        categoria_id=product_category["id"],
                        atributo_id=attribute_id,
                        valor_ids=[active_value["id"]],
                    )

        for attribute_id, mapping in effective.items():
            if not mapping["obligatorio"]:
                continue
            attribute = attribute_by_id[attribute_id]
            existing_values = values_by_key[(product["id"], attribute_id)]
            if (
                len(existing_values) == 1
                and (product["id"], attribute_id) not in pending_remaps
                and valid_value(attribute, existing_values[0])
            ):
                continue
            issue(
                "PRODUCT_REQUIRED_ATTRIBUTES_MISSING",
                "El producto no tiene un valor activo valido para un atributo obligatorio efectivo.",
                [product],
                categoria_id=product_category["id"],
                ruta=category_path(product_category["id"]),
                atributo_id=attribute_id,
                atributo_nombre=attribute["nombre"],
                mapping_id=mapping["id"],
                valor_ids=sorted(value["id"] for value in existing_values),
            )

    for raw_attribute_id, unit_code in sorted((unit_candidates or {}).items()):
        candidate_id = _identifier(raw_attribute_id)
        candidate_attribute = attribute_by_id.get(candidate_id)
        if (
            candidate_attribute is None
            or _normalized(candidate_attribute["tipo_dato"]) not in {"integer", "decimal"}
            or not str(unit_code).strip()
            or candidate_attribute.get("unidad_id") is not None
        ):
            issue(
                "UNIT_ANNOTATION_CANDIDATE_INVALID",
                "La anotacion debe identificar un atributo numerico sin unidad y una unidad explicita.",
                [{"id": candidate_id}],
                unidad_codigo_propuesto=unit_code,
            )
            continue
        historical_values = [
            value
            for value in rows["tbl_producto_atributo_valor"]
            if value["atributo_id"] == candidate_id
        ]
        historical_snapshots = [
            change
            for change in rows.get("tbl_atributo_cambio", [])
            if change["atributo_id"] == candidate_id
        ]
        report["candidatos_anotacion_unidad"].append(
            {
                "atributo_id": candidate_id,
                "atributo_nombre": candidate_attribute["nombre"],
                "unidad_codigo_propuesto": unit_code,
                "valores_activos": sum(bool(value["activo"]) for value in historical_values),
                "valores_historicos": len(historical_values),
                "snapshots_historicos": len(historical_snapshots),
                "producto_ids": sorted({value["producto_id"] for value in historical_values}),
                "requiere_confirmacion": bool(historical_values or historical_snapshots),
                "unidad_destino_validada": False,
            }
        )

    conflicts.sort(key=lambda conflict: (conflict["code"], conflict["ids"]))
    report["total_conflictos"] = len(conflicts)
    report["apto_para_migrar"] = not conflicts
    return report
