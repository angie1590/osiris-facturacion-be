from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Sequence
from osiris.domain.service import BaseService
from uuid import UUID
from osiris.core.audit import record_domain_change
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select
from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION

from osiris.modules.common.catalogo.entity import Catalogo
from osiris.modules.common.catalogo.entity import CatalogoValor
from osiris.modules.common.unidad.entity import Unidad
from osiris.utils.attribute_code import generate_attribute_code
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.inventario.categoria_atributo.service import (
    CategoriaAtributoService,
)
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria.resolver import (
    get_effective_attributes_by_category,
)
from osiris.modules.inventario.producto.models_atributos import (
    ProductoAtributoRemapeo,
    ProductoAtributoValor,
)
from osiris.modules.inventario.producto.service_atributos import (
    ProductoAtributoValorService,
)
from .repository import AtributoRepository
from .entity import Atributo, AtributoCambio, TipoDato


class AtributoService(BaseService[Atributo]):
    repo = AtributoRepository()
    _DEFINITION_FIELDS = (
        "nombre",
        "codigo",
        "unidad_id",
        "tipo_dato",
        "select_options",
        "catalog_id",
        "allow_negative",
        "min_value",
        "max_value",
        "activo",
    )

    @staticmethod
    def _reject_code_input(values: dict[str, Any]) -> None:
        if "codigo" in values:
            raise HTTPException(
                status_code=422,
                detail={"code": "ATTRIBUTE_CODE_IMMUTABLE", "message": "codigo es de solo lectura."},
            )

    @staticmethod
    def _validate_unique_code(session: Session, code: str) -> None:
        statement = (
            select(Atributo)
            .where(func.lower(func.trim(col(Atributo.codigo))) == code)
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        )
        if session.exec(statement.limit(1)).first() is not None:
            raise AtributoRepository.duplicate_code()

    @staticmethod
    def _validate_unit(session: Session, data: dict[str, Any]) -> None:
        unit_id = data.get("unidad_id")
        if unit_id is None:
            return
        if data["tipo_dato"] not in {TipoDato.INTEGER, TipoDato.DECIMAL}:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "ATTRIBUTE_UNIT_INVALID_TYPE",
                    "message": "La unidad solo aplica a atributos integer o decimal.",
                },
            )
        unit = session.exec(
            select(Unidad)
            .where(col(Unidad.id) == unit_id)
            .with_for_update()
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        ).first()
        if unit is None:
            raise HTTPException(status_code=404, detail="Unidad no encontrada.")
        if not unit.activo:
            raise HTTPException(
                status_code=409,
                detail={"code": "UNIT_INACTIVE", "message": "La unidad esta inactiva."},
            )

    @staticmethod
    def _guard_unit_change(
        session: Session,
        attribute: Atributo,
        target: dict[str, Any],
        state: dict[str, Any],
        *,
        allow_annotation: bool = False,
    ) -> None:
        if attribute.unidad_id == target.get("unidad_id"):
            return
        snapshots = session.exec(
            select(AtributoCambio).where(col(AtributoCambio.atributo_id) == attribute.id)
        ).all()
        has_history = AtributoService._has_unit_history(state, snapshots)
        if not has_history:
            return
        if attribute.unidad_id is None:
            if target.get("unidad_id") is not None and allow_annotation:
                return
            code = "ATTRIBUTE_UNIT_ANNOTATION_REQUIRES_CONFIRMATION"
        elif target.get("unidad_id") is None:
            code = "ATTRIBUTE_UNIT_REMOVAL_REQUIRES_MIGRATION"
        else:
            code = "ATTRIBUTE_UNIT_CHANGE_REQUIRES_CONVERSION"
        unit_counts = AtributoService._unit_history_counts(state, snapshots)
        raise HTTPException(
            status_code=409,
            detail={
                "code": code,
                "message": "El cambio de unidad con historia esta bloqueado hasta la entrega 6.",
                "conteos": unit_counts,
                "acciones_permitidas": ["anotar_unidad", "migrar_valores", "cancelar"],
            },
        )

    @staticmethod
    def _has_unit_history(
        state: dict[str, Any], snapshots: Sequence[AtributoCambio]
    ) -> bool:
        return bool(state["valores"] or state["remapeos"]) or any(
            assignment["valor_default"] is not None
            for assignment in state["asignaciones"]
        ) or any(
            snapshot.valores_anteriores
            or snapshot.valores_posteriores
            or snapshot.remapeos_anteriores
            or snapshot.remapeos_posteriores
            or snapshot.definicion_anterior.get("unidad_id") is not None
            or snapshot.definicion_posterior.get("unidad_id") is not None
            or any(
                assignment["valor_default"] is not None
                for assignment in (
                    snapshot.asignaciones_anteriores + snapshot.asignaciones_posteriores
                )
            )
            for snapshot in snapshots
        )

    @staticmethod
    def _unit_history_counts(
        state: dict[str, Any], snapshots: Sequence[AtributoCambio]
    ) -> dict[str, int]:
        current_values = state["valores"]
        historical_values: dict[str, dict[str, Any]] = {}
        historical_products: set[str] = set()
        defaults_historical = 0
        for snapshot in snapshots:
            for value in snapshot.valores_anteriores + snapshot.valores_posteriores:
                if value.get("id"):
                    historical_values[str(value["id"])] = value
                if value.get("producto_id"):
                    historical_products.add(str(value["producto_id"]))
            defaults_historical += sum(
                1
                for assignment in (
                    snapshot.asignaciones_anteriores
                    + snapshot.asignaciones_posteriores
                )
                if assignment.get("valor_default") is not None
            )
        current_products = {
            str(value["producto_id"])
            for value in current_values
            if value.get("producto_id")
        }
        return {
            "valores_activos": sum(1 for value in current_values if value["activo"]),
            "valores_inactivos": sum(1 for value in current_values if not value["activo"]),
            "valores_historicos": len(historical_values),
            "snapshots_historicos": len(snapshots),
            "defaults_actuales": sum(
                1
                for assignment in state["asignaciones"]
                if assignment["valor_default"] is not None
            ),
            "defaults_historicos": defaults_historical,
            "productos_afectados": len(current_products | historical_products),
        }

    def _capture_unit_annotation_state(
        self, session: Session, attribute: Atributo, *, lock: bool = False
    ) -> tuple[dict[str, Any], list[AtributoCambio]]:
        state = self._capture_state(session, attribute, lock=lock)
        statement = select(AtributoCambio).where(
            col(AtributoCambio.atributo_id) == attribute.id
        )
        if lock:
            statement = statement.with_for_update()
        snapshots = list(session.exec(statement).all())
        snapshots.sort(key=lambda snapshot: str(snapshot.id))
        state["unit_snapshots"] = [
            snapshot.model_dump(mode="json") for snapshot in snapshots
        ]
        return state, snapshots

    def _unit_annotation_details(
        self,
        session: Session,
        attribute: Atributo,
        target: dict[str, Any],
        state: dict[str, Any],
        snapshots: list[AtributoCambio],
    ) -> dict[str, Any] | None:
        if attribute.unidad_id is not None or target.get("unidad_id") is None:
            return None
        if not self._has_unit_history(state, snapshots):
            return None

        snapshot_values: dict[str, dict[str, Any]] = {}
        snapshot_products: set[str] = set()
        historical_defaults = 0
        for snapshot in snapshots:
            for value in snapshot.valores_anteriores + snapshot.valores_posteriores:
                value_id = str(value.get("id", ""))
                if value_id:
                    snapshot_values[value_id] = value
                if value.get("producto_id"):
                    snapshot_products.add(str(value["producto_id"]))
            historical_defaults += sum(
                1
                for assignment in (
                    snapshot.asignaciones_anteriores
                    + snapshot.asignaciones_posteriores
                )
                if assignment.get("valor_default") is not None
            )
        current_values = state["valores"]
        current_products = {
            str(value["producto_id"])
            for value in current_values
            if value.get("producto_id")
        }
        unit = session.get(Unidad, target["unidad_id"])
        return {
            "unidad": {
                "id": str(target["unidad_id"]),
                "nombre": unit.nombre if unit is not None else "Unidad",
                "simbolo": unit.simbolo if unit is not None else "",
            },
            "conteos": {
                "valores_activos": sum(1 for value in current_values if value["activo"]),
                "valores_inactivos": sum(1 for value in current_values if not value["activo"]),
                "valores_historicos": len(snapshot_values),
                "defaults_actuales": sum(
                    1
                    for assignment in state["asignaciones"]
                    if assignment["valor_default"] is not None
                ),
                "defaults_historicos": historical_defaults,
                "productos_afectados": len(current_products | snapshot_products),
            },
            "requiere_confirmacion": True,
        }

    @staticmethod
    def _validate_unique_name(
        session: Session,
        nombre: str,
        exclude_id: UUID | None = None,
    ) -> None:
        normalized_name = nombre.strip().casefold()
        if not normalized_name:
            return
        statement = select(col(Atributo.id)).where(
            col(Atributo.activo).is_(True),
            func.lower(func.trim(col(Atributo.nombre))) == normalized_name,
        )
        if exclude_id is not None:
            statement = statement.where(col(Atributo.id) != exclude_id)
        if session.exec(statement.limit(1)).first() is not None:
            raise HTTPException(
                status_code=409,
                detail="Ya existe un atributo activo con ese nombre.",
            )

    def create_for_category(
        self,
        session: Session,
        data: dict[str, Any],
        *,
        commit: bool = True,
    ) -> Atributo:
        values = self._ensure_dict(data).copy()
        categoria_id = values.pop("categoria_id")
        assignment_values = {
            "orden": values.pop("orden", None),
            "obligatorio": values.pop("obligatorio", False),
            "valor_default": values.pop("valor_default", None),
            "aplicar_default_a_existentes": values.pop(
                "aplicar_default_a_existentes", False
            ),
            "usuario_auditoria": values.get("usuario_auditoria"),
        }
        try:
            attribute = self.create(session, values, commit=False)
            CategoriaAtributoService().assign_existing(
                session,
                categoria_id,
                {
                    **assignment_values,
                    "atributo_id": attribute.id,
                },
                usuario_auditoria=assignment_values["usuario_auditoria"],
                commit=False,
            )
            if commit and isinstance(session, Session):
                session.commit()
                session.refresh(attribute)
            return attribute
        except Exception as exc:
            self._handle_transaction_error(session, exc)

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

    @classmethod
    def _serialize_definition(cls, attribute: Atributo) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for field in cls._DEFINITION_FIELDS:
            value = getattr(attribute, field)
            if field == "tipo_dato":
                value = value.value
            elif field in {"catalog_id", "unidad_id"} and value is not None:
                value = str(value)
            elif field in {"min_value", "max_value"} and value is not None:
                value = str(value)
            result[field] = value
        return result

    @classmethod
    def _serialize_definition_from_values(
        cls, values: dict[str, Any]
    ) -> dict[str, Any]:
        result = {field: values.get(field) for field in cls._DEFINITION_FIELDS}
        tipo = result.get("tipo_dato")
        if isinstance(tipo, TipoDato):
            result["tipo_dato"] = tipo.value
        for field in ("catalog_id", "unidad_id"):
            if result[field] is not None:
                result[field] = str(result[field])
        for field in ("min_value", "max_value"):
            if result[field] is not None:
                result[field] = str(result[field])
        result["activo"] = bool(result.get("activo", True))
        return result

    @staticmethod
    def _serialize_value(row: ProductoAtributoValor) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "producto_id": str(row.producto_id),
            "atributo_id": str(row.atributo_id),
            "valor_string": row.valor_string,
            "valor_integer": row.valor_integer,
            "valor_decimal": (
                str(row.valor_decimal) if row.valor_decimal is not None else None
            ),
            "valor_boolean": row.valor_boolean,
            "valor_date": (
                row.valor_date.isoformat() if row.valor_date is not None else None
            ),
            "activo": row.activo,
        }

    @staticmethod
    def _serialize_assignment(row: CategoriaAtributo) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "categoria_id": str(row.categoria_id),
            "atributo_id": str(row.atributo_id),
            "orden": row.orden,
            "obligatorio": row.obligatorio,
            "valor_default": row.valor_default,
            "activo": row.activo,
        }

    @staticmethod
    def _serialize_remap(row: ProductoAtributoRemapeo) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "producto_id": str(row.producto_id),
            "atributo_id": str(row.atributo_id),
            "tipo_anterior": row.tipo_anterior,
            "tipo_nuevo": row.tipo_nuevo,
            "valor_anterior": row.valor_anterior,
            "motivo": row.motivo,
            "activo": row.activo,
        }

    def _capture_state(
        self, session: Session, attribute: Atributo, *, lock: bool = False
    ) -> dict[str, Any]:
        def rows(model: Any, field: str) -> Sequence[Any]:
            statement = (
                select(model)
                .where(col(getattr(model, field)) == attribute.id)
                .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
            )
            if lock:
                statement = statement.with_for_update()
            return session.exec(statement).all()

        values = sorted(
            (
                self._serialize_value(row)
                for row in rows(ProductoAtributoValor, "atributo_id")
            ),
            key=lambda row: row["id"],
        )
        assignments = sorted(
            (
                self._serialize_assignment(row)
                for row in rows(CategoriaAtributo, "atributo_id")
            ),
            key=lambda row: row["id"],
        )
        reverted_snapshots = session.exec(
            select(AtributoCambio).where(
                col(AtributoCambio.atributo_id) == attribute.id,
                col(AtributoCambio.revertido).is_(True),
            )
        ).all()
        reversed_remap_ids = {
            remap["id"]
            for snapshot in reverted_snapshots
            for remap in snapshot.remapeos_posteriores
            if remap["id"]
            not in {previous["id"] for previous in snapshot.remapeos_anteriores}
        }
        remaps = sorted(
            (
                self._serialize_remap(row)
                for row in rows(ProductoAtributoRemapeo, "atributo_id")
                if str(row.id) not in reversed_remap_ids
            ),
            key=lambda row: row["id"],
        )
        return {
            "definicion": self._serialize_definition(attribute),
            "valores": values,
            "asignaciones": assignments,
            "remapeos": remaps,
        }

    @staticmethod
    def _has_pending_remaps(state: dict[str, Any]) -> bool:
        return any(remap["activo"] for remap in state["remapeos"])

    def _create_snapshot(
        self,
        session: Session,
        attribute: Atributo,
        operation: str,
        before: dict[str, Any],
        after: dict[str, Any],
    ) -> AtributoCambio:
        snapshot = AtributoCambio(
            atributo_id=attribute.id,
            operacion=operation,
            definicion_anterior=before["definicion"],
            definicion_posterior=after["definicion"],
            asignaciones_anteriores=before["asignaciones"],
            asignaciones_posteriores=after["asignaciones"],
            valores_anteriores=before["valores"],
            valores_posteriores=after["valores"],
            remapeos_anteriores=before["remapeos"],
            remapeos_posteriores=after["remapeos"],
        )
        session.add(snapshot)
        session.flush()
        return snapshot

    def _convert_value(
        self,
        session: Session,
        old_value: Any,
        target: dict[str, Any],
    ) -> tuple[str, Any]:
        new_type: TipoDato = target["tipo_dato"]
        field_name, new_value = ProductoAtributoValorService()._cast_by_tipo(
            new_type, old_value
        )
        if new_type == TipoDato.SELECT:
            matched = next(
                (
                    option
                    for option in (target.get("select_options") or [])
                    if option.casefold() == str(new_value).casefold()
                ),
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
            if (
                target.get("min_value") is not None
                and decimal_value < target["min_value"]
            ):
                raise ValueError("below configured minimum")
            if (
                target.get("max_value") is not None
                and decimal_value > target["max_value"]
            ):
                raise ValueError("above configured maximum")
        return field_name, new_value

    def _convert_existing_values(
        self,
        session: Session,
        attribute: Atributo,
        target: dict[str, Any],
    ) -> tuple[int, list[UUID]]:
        old_type = attribute.tipo_dato
        new_type = target["tipo_dato"]
        rows = list(
            session.exec(
                select(ProductoAtributoValor)
                .where(
                    col(ProductoAtributoValor.atributo_id) == attribute.id,
                    col(ProductoAtributoValor.activo).is_(True),
                )
                .with_for_update()
            ).all()
        )
        value_service = ProductoAtributoValorService()
        converted = 0
        pending_ids: list[UUID] = []
        for row in rows:
            old_value = self._value_from_row(row, old_type)
            try:
                field_name, new_value = self._convert_value(session, old_value, target)
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
                        before={
                            "valor": self._json_value(old_value),
                            "tipo": old_type.value,
                        },
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

    def _normalize_definition(
        self, session: Session, data: dict[str, Any]
    ) -> dict[str, Any]:
        tipo = data.get("tipo_dato")
        if not isinstance(tipo, TipoDato):
            try:
                tipo = TipoDato(str(tipo).lower())
            except ValueError:
                raise HTTPException(
                    status_code=400, detail="Tipo de dato de atributo no soportado."
                ) from None
        data["tipo_dato"] = tipo
        self._validate_unit(session, data)

        if tipo == TipoDato.SELECT:
            options = [
                str(option).strip()
                for option in (data.get("select_options") or [])
                if str(option).strip()
            ]
            if not options:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "SELECT_REQUIRES_OPTIONS",
                        "message": "Un atributo select requiere al menos una opción.",
                    },
                )
            normalized = [option.casefold() for option in options]
            if len(normalized) != len(set(normalized)):
                raise HTTPException(
                    status_code=400,
                    detail="Las opciones del atributo no pueden repetirse.",
                )
            data["select_options"] = options
            data["catalog_id"] = None
        elif tipo == TipoDato.CATALOG:
            data["select_options"] = None
            catalog_id = data.get("catalog_id")
            if catalog_id is not None:
                catalog = session.get(Catalogo, catalog_id)
                if not catalog or not catalog.activo:
                    raise HTTPException(
                        status_code=404,
                        detail="Catálogo de atributos no encontrado o inactivo.",
                    )
            else:
                catalog_name = self._pluralize_es(data.get("nombre", ""))
                catalog = session.exec(
                    select(Catalogo).where(
                        func.lower(Catalogo.nombre) == catalog_name.lower()
                    )
                ).first()
                if catalog is None:
                    catalog = Catalogo(
                        nombre=catalog_name, usuario_auditoria="api", activo=True
                    )
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
        data["allow_negative"] = (
            bool(data.get("allow_negative", False)) if numeric_type else False
        )
        minimum = data.get("min_value")
        maximum = data.get("max_value")
        if not numeric_type and (minimum is not None or maximum is not None):
            raise HTTPException(
                status_code=400,
                detail="Los límites numéricos solo aplican a atributos integer o decimal.",
            )
        if minimum is not None and maximum is not None and minimum > maximum:
            raise HTTPException(
                status_code=400, detail="min_value no puede ser mayor que max_value."
            )
        return data

    def create(
        self,
        session: Session,
        data: dict[str, Any],
        *,
        commit: bool = True,
    ) -> Atributo:
        values = self._ensure_dict(data).copy()
        try:
            self._reject_code_input(values)
            try:
                code = generate_attribute_code(str(values.get("nombre", "")))
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            self._validate_unique_code(session, code)
            values["codigo"] = code
            self._validate_unique_name(session, str(values.get("nombre", "")))
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
                        "codigo": attribute.codigo,
                        "unidad_id": str(attribute.unidad_id) if attribute.unidad_id else None,
                        "tipo_dato": attribute.tipo_dato.value,
                        "catalog_id": (
                            str(attribute.catalog_id) if attribute.catalog_id else None
                        ),
                    },
                )
            if commit and isinstance(session, Session):
                session.commit()
                session.refresh(attribute)
            return attribute
        except Exception as exc:
            try:
                self._handle_transaction_error(session, exc)
            except HTTPException as error:
                cause: BaseException | None = error
                while cause is not None:
                    if isinstance(cause, IntegrityError):
                        if "codigo" in values:
                            self._validate_unique_code(session, values["codigo"])
                        break
                    cause = cause.__cause__
                raise

    def update(
        self,
        session: Session,
        item_id: UUID,
        data: Any,
        *,
        commit: bool = True,
        allow_unit_annotation: bool = False,
    ) -> Atributo | None:
        values = self._ensure_dict(data).copy()
        values.pop("confirmar_anotacion_unidad", None)
        values.pop("precondicion_preview", None)
        try:
            if isinstance(session, Session):
                from osiris.modules.inventario.categoria.service import CategoriaService

                CategoriaService.acquire_hierarchy_mutation_lock(session)
            self._reject_code_input(values)
            current = session.exec(
                select(Atributo).where(col(Atributo.id) == item_id).with_for_update()
            ).first()
            if current is None:
                return None
            merged = {
                "nombre": values.get("nombre", current.nombre),
                "codigo": current.codigo,
                "unidad_id": values.get("unidad_id", current.unidad_id),
                "tipo_dato": values.get("tipo_dato", current.tipo_dato),
                "select_options": values.get("select_options", current.select_options),
                "catalog_id": values.get("catalog_id", current.catalog_id),
                "allow_negative": values.get("allow_negative", current.allow_negative),
                "min_value": values.get("min_value", current.min_value),
                "max_value": values.get("max_value", current.max_value),
            }
            self._validate_unique_name(
                session, str(merged["nombre"]), exclude_id=item_id
            )
            normalized = self._normalize_definition(session, merged)
            values.update(normalized)
            definition_changed = any(
                getattr(current, field) != normalized[field]
                for field in self._DEFINITION_FIELDS[:-1]
            )
            if not definition_changed:
                return current
            before_state = self._capture_state(session, current, lock=True)
            self._guard_unit_change(
                session,
                current,
                normalized,
                before_state,
                allow_annotation=allow_unit_annotation,
            )
            is_unit_annotation = (
                current.unidad_id is None and normalized.get("unidad_id") is not None
            )
            conversion_fields = {
                "tipo_dato",
                "select_options",
                "catalog_id",
                "allow_negative",
                "min_value",
                "max_value",
            }
            conversion_changed = any(
                getattr(current, field) != normalized[field]
                for field in conversion_fields
            )
            if conversion_changed and self._has_pending_remaps(before_state):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "ATTRIBUTE_HAS_PENDING_REMAPS",
                        "message": "Resuelve o revierte los remapeos pendientes antes de cambiar la definición del atributo.",
                    },
                )
            converted_count = 0
            pending_remaps: list[UUID] = []
            if conversion_changed and isinstance(session, Session):
                self._assert_required_conversion_preserves_values(
                    session, current, normalized
                )
                converted_count, pending_remaps = self._convert_existing_values(
                    session, current, normalized
                )
            before = before_state["definicion"]
            attribute: Atributo | None = super().update(
                session, item_id, values, commit=False
            )
            if attribute is None:
                return None
            if isinstance(session, Session):
                after_state = self._capture_state(session, attribute, lock=True)
                snapshot = self._create_snapshot(
                    session,
                    attribute,
                    "annotate_unit" if is_unit_annotation else "update",
                    before_state,
                    after_state,
                )
                record_domain_change(
                    session,
                    entity="tbl_atributo",
                    entity_id=item_id,
                    action=(
                        "ANNOTATE_ATTRIBUTE_UNIT"
                        if is_unit_annotation
                        else "UPDATE_ATTRIBUTE"
                    ),
                    before=before,
                    after={
                        **after_state["definicion"],
                        "converted_values": converted_count,
                        "pending_remap_ids": [
                            str(remap_id) for remap_id in pending_remaps
                        ],
                        "snapshot_id": str(snapshot.id),
                    },
                )
            if commit and isinstance(session, Session):
                session.commit()
                session.refresh(attribute)
            return attribute
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    def _assert_required_conversion_preserves_values(
        self, session: Session, attribute: Atributo, target: dict[str, Any]
    ) -> None:
        active_rows = session.exec(
            select(ProductoAtributoValor).where(
                col(ProductoAtributoValor.atributo_id) == attribute.id,
                col(ProductoAtributoValor.activo).is_(True),
            )
        ).all()
        incompatible_ids: set[UUID] = set()
        for row in active_rows:
            old_value = self._value_from_row(row, attribute.tipo_dato)
            try:
                self._convert_value(session, old_value, target)
            except (ValueError, TypeError, InvalidOperation, KeyError):
                incompatible_ids.add(row.producto_id)
        if not incompatible_ids:
            return

        required_mappings = session.exec(
            select(CategoriaAtributo).where(
                col(CategoriaAtributo.atributo_id) == attribute.id,
                col(CategoriaAtributo.activo).is_(True),
                col(CategoriaAtributo.obligatorio).is_(True),
            )
        ).all()
        affected_required: set[UUID] = set()
        names: dict[UUID, str] = {}
        mapping_service = CategoriaAtributoService()
        for mapping in required_mappings:
            _, affected_ids, _, product_names = mapping_service.required_attribute_impact(
                session, mapping
            )
            affected_required.update(set(affected_ids) & incompatible_ids)
            names.update(product_names)
        if affected_required:
            mapping_service._raise_required_attribute_missing(
                sorted(affected_required, key=str), names
            )

    def delete(
        self, session: Session, item_id: UUID, *, commit: bool = True
    ) -> bool | None:
        try:
            if isinstance(session, Session):
                from osiris.modules.inventario.categoria.service import CategoriaService

                CategoriaService.acquire_hierarchy_mutation_lock(session)
            attribute: Atributo | None = session.exec(
                select(Atributo).where(col(Atributo.id) == item_id).with_for_update()
            ).first()
            if attribute is None:
                return None
            before_state = self._capture_state(session, attribute, lock=True)
            pending = [remap for remap in before_state["remapeos"] if remap["activo"]]
            if pending:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "ATTRIBUTE_HAS_PENDING_REMAPS",
                        "message": "Resuelve o revierte los remapeos pendientes antes de dar de baja el atributo.",
                        "remapeos_pendientes": len(pending),
                    },
                )
            assignments = session.exec(
                select(CategoriaAtributo)
                .where(col(CategoriaAtributo.atributo_id) == item_id)
                .with_for_update()
                .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
            ).all()
            values = session.exec(
                select(ProductoAtributoValor)
                .where(col(ProductoAtributoValor.atributo_id) == item_id)
                .with_for_update()
                .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
            ).all()
            attribute.activo = False
            session.add(attribute)
            for row in assignments:
                if row.activo:
                    row.activo = False
                    session.add(row)
            for value_row in values:
                if value_row.activo:
                    value_row.activo = False
                    session.add(value_row)
            after_state = self._capture_state(session, attribute, lock=True)
            snapshot = self._create_snapshot(
                session, attribute, "deactivate", before_state, after_state
            )
            if isinstance(session, Session):
                record_domain_change(
                    session,
                    entity="tbl_atributo",
                    entity_id=item_id,
                    action="DELETE_ATTRIBUTE",
                    before=before_state["definicion"],
                    after={"activo": False, "snapshot_id": str(snapshot.id)},
                )
            if commit and isinstance(session, Session):
                session.commit()
            else:
                session.flush()
            return True
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    def preview_update(
        self, session: Session, item_id: UUID, data: Any
    ) -> dict[str, Any] | None:
        values = self._ensure_dict(data).copy()
        self._reject_code_input(values)
        attribute = self.repo.get(session, item_id)
        if attribute is None:
            return None

        target = {
            "nombre": values.get("nombre", attribute.nombre),
            "codigo": attribute.codigo,
            "unidad_id": values.get("unidad_id", attribute.unidad_id),
            "tipo_dato": values.get("tipo_dato", attribute.tipo_dato),
            "select_options": values.get("select_options", attribute.select_options),
            "catalog_id": values.get("catalog_id", attribute.catalog_id),
            "allow_negative": values.get("allow_negative", attribute.allow_negative),
            "min_value": values.get("min_value", attribute.min_value),
            "max_value": values.get("max_value", attribute.max_value),
        }
        try:
            target["tipo_dato"] = (
                TipoDato(str(target["tipo_dato"]).lower())
                if not isinstance(target["tipo_dato"], TipoDato)
                else target["tipo_dato"]
            )
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Tipo de dato de atributo no soportado."
            ) from None
        self._validate_unique_name(session, str(target["nombre"]), exclude_id=item_id)
        self._validate_unit(session, target)

        tipo = target["tipo_dato"]
        if tipo == TipoDato.SELECT:
            options = [
                str(option).strip()
                for option in (target["select_options"] or [])
                if str(option).strip()
            ]
            if not options or len({option.casefold() for option in options}) != len(
                options
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Las opciones select deben existir y ser únicas.",
                )
            target["select_options"] = options
            target["catalog_id"] = None
        elif tipo == TipoDato.CATALOG:
            target["select_options"] = None
            catalog_id = target["catalog_id"]
            catalog = (
                session.get(Catalogo, catalog_id)
                if catalog_id
                else session.exec(
                    select(Catalogo).where(
                        func.lower(col(Catalogo.nombre))
                        == self._pluralize_es(str(target["nombre"])).lower()
                    )
                ).first()
            )
            if catalog_id and (catalog is None or not catalog.activo):
                raise HTTPException(
                    status_code=400,
                    detail="El catálogo de destino debe existir y estar activo.",
                )
            target["catalog_id"] = catalog.id if catalog is not None else None
        else:
            target["select_options"] = None
            target["catalog_id"] = None

        numeric_type = tipo in {TipoDato.INTEGER, TipoDato.DECIMAL}
        target["allow_negative"] = (
            bool(target["allow_negative"]) if numeric_type else False
        )
        minimum = (
            Decimal(str(target["min_value"]))
            if target["min_value"] is not None
            else None
        )
        maximum = (
            Decimal(str(target["max_value"]))
            if target["max_value"] is not None
            else None
        )
        if not numeric_type and (minimum is not None or maximum is not None):
            raise HTTPException(
                status_code=400,
                detail="Los límites numéricos solo aplican a integer o decimal.",
            )
        if minimum is not None and maximum is not None and minimum > maximum:
            raise HTTPException(
                status_code=400, detail="min_value no puede ser mayor que max_value."
            )
        target["min_value"] = minimum
        target["max_value"] = maximum

        before_state, unit_snapshots = self._capture_unit_annotation_state(
            session, attribute
        )
        unit_annotation = self._unit_annotation_details(
            session, attribute, target, before_state, unit_snapshots
        )
        changed_fields = {
            field
            for field in self._DEFINITION_FIELDS[:-1]
            if getattr(attribute, field) != target[field]
        }
        if unit_annotation is not None and changed_fields - {"unidad_id"}:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "ATTRIBUTE_UNIT_ANNOTATION_REQUIRES_CONFIRMATION",
                    "message": "Confirma la anotación de unidad por separado de otros cambios de definición.",
                    "conteos": unit_annotation["conteos"],
                    "acciones_permitidas": ["anotar_unidad", "cancelar"],
                },
            )
        self._guard_unit_change(
            session,
            attribute,
            target,
            before_state,
            allow_annotation=True,
        )
        changed = any(
            getattr(attribute, field) != target[field]
            for field in (
                "tipo_dato",
                "select_options",
                "catalog_id",
                "allow_negative",
                "min_value",
                "max_value",
            )
        )
        if changed and self._has_pending_remaps(before_state):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "ATTRIBUTE_HAS_PENDING_REMAPS",
                    "message": "Resuelve o revierte los remapeos pendientes antes de cambiar la definición del atributo.",
                },
            )

        rows = session.exec(
            select(ProductoAtributoValor).where(
                col(ProductoAtributoValor.atributo_id) == item_id,
                col(ProductoAtributoValor.activo).is_(True),
            )
        ).all()
        incompatible: list[dict[str, Any]] = []
        converted = 0
        for row in rows if changed else []:
            old_value = self._value_from_row(row, attribute.tipo_dato)
            try:
                self._convert_value(session, old_value, target)
                converted += 1
            except (ValueError, TypeError, InvalidOperation, KeyError) as exc:
                incompatible.append(
                    {
                        "producto_id": str(row.producto_id),
                        "valor": self._json_value(old_value),
                        "motivo": str(exc),
                    }
                )
        if changed and incompatible:
            self._assert_required_conversion_preserves_values(
                session, attribute, target
            )
        active_categories = session.exec(
            select(col(Categoria.id), col(Categoria.nombre)).where(
                col(Categoria.activo).is_(True)
            )
        ).all()
        category_names = {category_id: name for category_id, name in active_categories}
        effective_by_category = get_effective_attributes_by_category(
            session, list(category_names)
        )
        effective_categories = [
            {
                "categoria_id": str(category_id),
                "categoria_nombre": category_names[category_id],
                "mapping_id": str(mapping["mapping_id"]),
                "categoria_origen": {
                    "id": str(mapping["categoria_origen"]["id"]),
                    "nombre": mapping["categoria_origen"]["nombre"],
                },
                "profundidad": mapping["profundidad"],
            }
            for category_id, mappings in effective_by_category.items()
            for mapping in mappings
            if mapping["atributo_id"] == attribute.id
        ]
        effective_categories.sort(
            key=lambda item: (
                str(item["categoria_nombre"]).strip().casefold(),
                str(item["categoria_id"]),
            )
        )
        return {
            "atributo_id": str(item_id),
            "definicion_actual": before_state["definicion"],
            "definicion_propuesta": self._serialize_definition_from_values(
                {**target, "activo": attribute.activo}
            ),
            "valores_activos": len(rows),
            "asignaciones_activas": sum(
                1 for assignment in before_state["asignaciones"] if assignment["activo"]
            ),
            "categorias_efectivas": effective_categories,
            "productos_afectados": len({str(row.producto_id) for row in rows}),
            "convertibles": converted,
            "incompatibles": incompatible,
            "remapeos_pendientes": sum(
                1 for remap in before_state["remapeos"] if remap["activo"]
            ),
            "requiere_confirmacion": bool(unit_annotation)
            or changed and bool(rows),
            "unidad_anotacion": unit_annotation,
            "resumen_anotacion_unidad": (
                f"Los valores y defaults existentes pasarán a interpretarse en "
                f"{unit_annotation['unidad']['nombre']} ({unit_annotation['unidad']['simbolo']}) "
                "sin modificar sus números."
                if unit_annotation is not None
                else None
            ),
        }

    @staticmethod
    def _restore_definition(attribute: Atributo, definition: dict[str, Any]) -> None:
        attribute.nombre = definition["nombre"]
        attribute.tipo_dato = TipoDato(definition["tipo_dato"])
        attribute.unidad_id = UUID(definition["unidad_id"]) if definition.get("unidad_id") else None
        attribute.select_options = definition["select_options"]
        attribute.catalog_id = (
            UUID(definition["catalog_id"]) if definition["catalog_id"] else None
        )
        attribute.allow_negative = definition["allow_negative"]
        attribute.min_value = (
            Decimal(definition["min_value"])
            if definition["min_value"] is not None
            else None
        )
        attribute.max_value = (
            Decimal(definition["max_value"])
            if definition["max_value"] is not None
            else None
        )
        attribute.activo = definition["activo"]

    @staticmethod
    def _compatible_snapshot_definition(
        attribute: Atributo, definition: dict[str, Any]
    ) -> dict[str, Any]:
        return {"codigo": attribute.codigo, "unidad_id": None, **definition}

    @staticmethod
    def _restore_rows(
        session: Session,
        model: Any,
        current: Sequence[Any],
        wanted: list[dict[str, Any]],
    ) -> None:
        by_id = {str(row.id): row for row in current}
        wanted_ids = {data["id"] for data in wanted}
        for row in current:
            if str(row.id) not in wanted_ids:
                raise HTTPException(
                    status_code=409,
                    detail="No se puede eliminar una fila histórica durante la reversión.",
                )
        for data in wanted:
            row = by_id.get(data["id"])
            if row is None:
                raise HTTPException(
                    status_code=409,
                    detail="No se puede restaurar una fila histórica eliminada.",
                )
            for field, value in data.items():
                if field == "id":
                    continue
                if (
                    field in {"producto_id", "atributo_id", "categoria_id"}
                    and value is not None
                ):
                    value = UUID(value)
                elif field == "valor_decimal" and value is not None:
                    value = Decimal(value)
                elif field == "valor_date" and value is not None:
                    value = date.fromisoformat(value)
                setattr(row, field, value)
            session.add(row)

    @staticmethod
    def _restore_remaps(
        session: Session,
        current: Sequence[ProductoAtributoRemapeo],
        wanted: list[dict[str, Any]],
    ) -> None:
        by_id = {str(row.id): row for row in current}
        wanted_ids = {data["id"] for data in wanted}
        for current_remap in current:
            if str(current_remap.id) not in wanted_ids:
                current_remap.activo = False
                session.add(current_remap)
        for data in wanted:
            remap = by_id.get(data["id"])
            if remap is None:
                raise HTTPException(
                    status_code=409,
                    detail="No se puede restaurar un remapeo histórico eliminado.",
                )
            remap.producto_id = UUID(data["producto_id"])
            remap.atributo_id = UUID(data["atributo_id"])
            remap.tipo_anterior = data["tipo_anterior"]
            remap.tipo_nuevo = data["tipo_nuevo"]
            remap.valor_anterior = data["valor_anterior"]
            remap.motivo = data["motivo"]
            remap.activo = data["activo"]
            session.add(remap)

    def lifecycle_status(
        self, session: Session, item_id: UUID
    ) -> dict[str, Any] | None:
        attribute = session.exec(
            select(Atributo)
            .where(col(Atributo.id) == item_id)
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        ).first()
        if attribute is None:
            return None
        snapshot = session.exec(
            select(AtributoCambio)
            .where(
                col(AtributoCambio.atributo_id) == item_id,
                col(AtributoCambio.revertido).is_(False),
            )
            .order_by(
                col(AtributoCambio.creado_en).desc(), col(AtributoCambio.id).desc()
            )
        ).first()
        if snapshot is None:
            reason = (
                "Este atributo inactivo no tiene snapshot de baja; requiere recuperación administrativa."
                if not attribute.activo
                else "No existe un snapshot reversible para este atributo."
            )
            return {
                "atributo_id": str(item_id),
                "can_undo": False,
                "can_reactivate": False,
                "operacion": None,
                "state_unchanged": False,
                "snapshot_id": None,
                "motivo": reason,
                "creado_en": None,
                "valores_afectados": 0,
                "categorias_afectadas": 0,
            }
        current_state = self._capture_state(session, attribute)
        expected_state = {
            "definicion": self._compatible_snapshot_definition(
                attribute, snapshot.definicion_posterior
            ),
            "asignaciones": snapshot.asignaciones_posteriores,
            "valores": snapshot.valores_posteriores,
            "remapeos": snapshot.remapeos_posteriores,
        }
        unchanged = current_state == expected_state
        changed_sections = [
            section
            for section in ("definicion", "asignaciones", "valores", "remapeos")
            if current_state[section] != expected_state[section]
        ]
        return {
            "atributo_id": str(item_id),
            "can_undo": unchanged,
            "can_reactivate": unchanged
            and snapshot.operacion == "deactivate"
            and not attribute.activo,
            "operacion": snapshot.operacion,
            "state_unchanged": unchanged,
            "snapshot_id": str(snapshot.id),
            "motivo": (
                None
                if unchanged
                else f"El estado cambió después de la operación: {', '.join(changed_sections)}."
            ),
            "creado_en": snapshot.creado_en.isoformat(),
            "valores_afectados": len(snapshot.valores_posteriores),
            "categorias_afectadas": sum(
                1
                for assignment in snapshot.asignaciones_posteriores
                if assignment["activo"]
            ),
        }

    def undo(
        self, session: Session, item_id: UUID, *, operation: str | None = None
    ) -> dict[str, Any] | None:
        try:
            if isinstance(session, Session):
                from osiris.modules.inventario.categoria.service import CategoriaService

                CategoriaService.acquire_hierarchy_mutation_lock(session)
            attribute = session.exec(
                select(Atributo)
                .where(col(Atributo.id) == item_id)
                .with_for_update()
                .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
            ).first()
            if attribute is None:
                return None
            statement = (
                select(AtributoCambio)
                .where(
                    col(AtributoCambio.atributo_id) == item_id,
                    col(AtributoCambio.revertido).is_(False),
                )
                .order_by(
                    col(AtributoCambio.creado_en).desc(), col(AtributoCambio.id).desc()
                )
                .with_for_update()
            )
            snapshot = session.exec(statement).first()
            if snapshot is None:
                if not attribute.activo:
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "code": "LEGACY_ATTRIBUTE_NO_SNAPSHOT",
                            "message": "Este atributo inactivo no tiene snapshot de baja; requiere recuperación administrativa.",
                        },
                    )
                raise HTTPException(
                    status_code=409,
                    detail="No hay cambios reversibles para este atributo.",
                )
            if operation is not None and snapshot.operacion != operation:
                raise HTTPException(
                    status_code=409,
                    detail="La última operación no corresponde a la acción solicitada.",
                )

            current_state = self._capture_state(session, attribute, lock=True)
            expected_state = {
                "definicion": self._compatible_snapshot_definition(
                    attribute, snapshot.definicion_posterior
                ),
                "asignaciones": snapshot.asignaciones_posteriores,
                "valores": snapshot.valores_posteriores,
                "remapeos": snapshot.remapeos_posteriores,
            }
            if current_state != expected_state:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "ATTRIBUTE_STATE_CHANGED",
                        "message": "El atributo o sus datos relacionados cambiaron después de esta operación; no se puede revertir con seguridad.",
                    },
                )

            assignments = session.exec(
                select(CategoriaAtributo)
                .where(col(CategoriaAtributo.atributo_id) == item_id)
                .with_for_update()
                .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
            ).all()
            values = session.exec(
                select(ProductoAtributoValor)
                .where(col(ProductoAtributoValor.atributo_id) == item_id)
                .with_for_update()
                .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
            ).all()
            remaps = session.exec(
                select(ProductoAtributoRemapeo)
                .where(col(ProductoAtributoRemapeo.atributo_id) == item_id)
                .with_for_update()
                .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
            ).all()
            self._restore_definition(attribute, snapshot.definicion_anterior)
            self._restore_rows(
                session,
                CategoriaAtributo,
                assignments,
                snapshot.asignaciones_anteriores,
            )
            self._restore_rows(
                session, ProductoAtributoValor, values, snapshot.valores_anteriores
            )
            self._restore_remaps(session, remaps, snapshot.remapeos_anteriores)
            snapshot.revertido = True
            snapshot.revertido_en = datetime.utcnow()
            session.add(attribute)
            session.add(snapshot)
            record_domain_change(
                session,
                entity="tbl_atributo",
                entity_id=item_id,
                action="UNDO_ATTRIBUTE_CHANGE",
                before=current_state["definicion"],
                after={
                    "snapshot_id": str(snapshot.id),
                    "restored": snapshot.definicion_anterior,
                },
            )
            session.commit()
            return {"snapshot_id": str(snapshot.id), "operacion": snapshot.operacion}
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    def reactivate(self, session: Session, item_id: UUID) -> dict[str, Any] | None:
        return self.undo(session, item_id, operation="deactivate")
