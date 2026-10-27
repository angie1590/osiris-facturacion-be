from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.catalogo.entity import Catalogo, CatalogoValor
from osiris.modules.common.unidad.entity import Unidad
from osiris.modules.inventario.atributo.entity import Atributo, AtributoCambio, TipoDato
from osiris.modules.inventario.atributo.models import (
    AtributoCreate,
    AtributoRead,
    AtributoUpdate,
)
from osiris.modules.inventario.atributo.service import AtributoService
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.inventario.producto.entity import Producto, ProductoCategoria
from osiris.modules.inventario.producto.models_atributos import (
    ProductoAtributoRemapeo,
    ProductoAtributoValor,
)
from osiris.utils.attribute_code import generate_attribute_code


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Memoria RAM", "memoria_ram"),
        ("  Tama\u00f1o / resoluci\u00f3n -- ", "tamano_resolucion"),
        ("---", "atributo"),
        ("\u4e2d\u6587", "atributo"),
        ("123 DPI", "atributo_123_dpi"),
        ("A__B", "a_b"),
        ("a" * 120, "a" * 120),
    ],
)
def test_generate_attribute_code(name, expected):
    assert generate_attribute_code(name) == expected


@pytest.mark.parametrize("name", ["a" * 121, "1" * 113])
def test_generate_attribute_code_rejects_overflow_without_truncating(name):
    with pytest.raises(ValueError, match="120"):
        generate_attribute_code(name)


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    SQLModel.metadata.create_all(
        engine,
        tables=[
            Unidad.__table__,
            AuditLog.__table__,
            Catalogo.__table__,
            CatalogoValor.__table__,
            CasaComercial.__table__,
            Categoria.__table__,
            Atributo.__table__,
            AtributoCambio.__table__,
            CategoriaAtributo.__table__,
            Producto.__table__,
            ProductoCategoria.__table__,
            ProductoAtributoValor.__table__,
            ProductoAtributoRemapeo.__table__,
        ],
    )
    with Session(engine) as database_session:
        yield database_session
    engine.dispose()


@pytest.fixture
def units(session):
    first = Unidad(
        codigo="GIGABYTE", nombre="Gigabyte", simbolo="GB", magnitud_codigo="DATA_STORAGE"
    )
    second = Unidad(
        codigo="MEGABYTE", nombre="Megabyte", simbolo="MB", magnitud_codigo="DATA_STORAGE"
    )
    session.add_all([first, second])
    session.commit()
    return first, second


def test_direct_orm_creation_generates_nonnull_stable_code(session):
    attribute = Atributo(nombre="Memoria RAM", tipo_dato=TipoDato.INTEGER)
    session.add(attribute)
    session.commit()
    assert attribute.codigo == "memoria_ram"
    attribute.nombre = "RAM instalada"
    session.commit()
    assert attribute.codigo == "memoria_ram"
    assert AtributoRead.model_validate(attribute).codigo == "memoria_ram"


@pytest.mark.parametrize("active", [True, False])
def test_generated_code_collision_includes_inactive_attributes(session, active):
    session.add(Atributo(nombre="Resolucion", tipo_dato=TipoDato.STRING, activo=active))
    session.commit()
    payload = {"nombre": "Resoluci\u00f3n", "tipo_dato": TipoDato.STRING}
    with pytest.raises(HTTPException) as error:
        AtributoService().create(session, payload)
    assert error.value.status_code == 409
    assert error.value.detail["code"] == "ATTRIBUTE_DUPLICATE_CODE"
    assert error.value.detail["conteos"] == {}
    assert error.value.detail["acciones_permitidas"] == []
    assert payload == {"nombre": "Resoluci\u00f3n", "tipo_dato": TipoDato.STRING}


def test_database_normalized_code_conflict_is_translated(session):
    session.add(Atributo(nombre="RAM", tipo_dato=TipoDato.INTEGER, activo=False))
    session.commit()
    session.add(Atributo(nombre="Otra RAM", codigo="ram", tipo_dato=TipoDato.INTEGER))
    with pytest.raises(IntegrityError) as error:
        session.flush()
    session.rollback()
    with pytest.raises(HTTPException) as translated:
        AtributoService.repo._raise_integrity(error.value)
    assert translated.value.status_code == 409
    assert translated.value.detail["code"] == "ATTRIBUTE_DUPLICATE_CODE"
    assert translated.value.detail["conteos"] == {}
    assert translated.value.detail["acciones_permitidas"] == []


@pytest.mark.parametrize("code", [" RAM ", "RAM", "ram__installed", "ram_"])
def test_database_rejects_noncanonical_code_format(session, code):
    session.add(Atributo(nombre="RAM", codigo=code, tipo_dato=TipoDato.INTEGER))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


@pytest.mark.parametrize("dto", [AtributoCreate, AtributoUpdate])
def test_dtos_reject_code_input(dto):
    with pytest.raises(ValidationError, match="codigo"):
        dto.model_validate({"nombre": "RAM", "tipo_dato": "integer", "codigo": "ram"})


@pytest.mark.parametrize("method", ["create", "update", "preview_update"])
def test_service_rejects_code_input(session, method):
    attribute = AtributoService().create(
        session, {"nombre": "RAM", "tipo_dato": TipoDato.INTEGER}
    )
    payload = {"nombre": "Nueva RAM", "tipo_dato": TipoDato.INTEGER, "codigo": "otra"}
    with pytest.raises(HTTPException) as error:
        if method == "create":
            AtributoService().create(session, payload)
        else:
            getattr(AtributoService(), method)(session, attribute.id, payload)
    assert error.value.status_code == 422
    session.refresh(attribute)
    assert attribute.codigo == "ram"
    assert attribute.nombre == "RAM"


def test_create_rejects_generated_code_overflow_in_dto_and_service(session):
    payload = {"nombre": "1" * 113, "tipo_dato": TipoDato.INTEGER}
    with pytest.raises(ValidationError, match="120"):
        AtributoCreate.model_validate(payload)
    with pytest.raises(HTTPException) as error:
        AtributoService().create(session, payload)
    assert error.value.status_code == 422
    assert "codigo" not in payload


@pytest.mark.parametrize("tipo", [TipoDato.INTEGER, TipoDato.DECIMAL])
def test_numeric_attribute_accepts_active_unit(session, units, tipo):
    attribute = AtributoService().create(
        session,
        {"nombre": "RAM", "tipo_dato": tipo, "unidad_id": units[0].id},
    )
    assert attribute.unidad_id == units[0].id
    assert AtributoRead.model_validate(attribute).unidad_id == units[0].id


@pytest.mark.parametrize(
    "tipo", [TipoDato.STRING, TipoDato.SELECT, TipoDato.CATALOG, TipoDato.BOOLEAN, TipoDato.DATE]
)
def test_non_numeric_unit_is_rejected_by_dto_and_service(session, units, tipo):
    payload = {"nombre": "SKU", "tipo_dato": tipo, "unidad_id": units[0].id}
    with pytest.raises(ValidationError, match="ATTRIBUTE_UNIT_INVALID_TYPE"):
        AtributoCreate.model_validate(payload)
    with pytest.raises(ValidationError, match="ATTRIBUTE_UNIT_INVALID_TYPE"):
        AtributoUpdate.model_validate(payload)
    with pytest.raises(HTTPException) as error:
        AtributoService().create(session, payload)
    assert error.value.detail["code"] == "ATTRIBUTE_UNIT_INVALID_TYPE"


def test_partial_update_validates_effective_type_and_preserves_unit(session, units):
    service = AtributoService()
    attribute = service.create(
        session, {"nombre": "RAM", "tipo_dato": TipoDato.INTEGER, "unidad_id": units[0].id}
    )
    with pytest.raises(HTTPException) as error:
        service.update(session, attribute.id, AtributoUpdate(tipo_dato=TipoDato.STRING))
    assert error.value.detail["code"] == "ATTRIBUTE_UNIT_INVALID_TYPE"
    session.refresh(attribute)
    assert attribute.tipo_dato == TipoDato.INTEGER
    assert attribute.unidad_id == units[0].id


def test_inactive_and_missing_units_are_rejected(session, units):
    units[0].activo = False
    session.commit()
    for unit_id, expected_status in [(units[0].id, 409), (uuid4(), 404)]:
        with pytest.raises(HTTPException) as error:
            AtributoService().create(
                session,
                {"nombre": "RAM", "tipo_dato": TipoDato.INTEGER, "unidad_id": unit_id},
            )
        assert error.value.status_code == expected_status
        if expected_status == 409:
            assert error.value.detail["code"] == "UNIT_INACTIVE"


@pytest.mark.parametrize("tipo", [TipoDato.STRING, TipoDato.BOOLEAN, TipoDato.DATE])
def test_database_rejects_non_numeric_unit(session, units, tipo):
    session.add(Atributo(nombre="SKU", tipo_dato=tipo, unidad_id=units[0].id))
    with pytest.raises(IntegrityError, match="ck_tbl_atributo_unidad_tipo_numerico"):
        session.flush()
    session.rollback()


def test_database_accepts_lowercase_legacy_and_uppercase_enum_numeric_types(session, units):
    attribute = Atributo(nombre="RAM", tipo_dato=TipoDato.INTEGER, unidad_id=units[0].id)
    session.add(attribute)
    session.commit()
    for tipo in ("integer", "INTEGER", "decimal", "DECIMAL"):
        session.execute(
            text("UPDATE tbl_atributo SET tipo_dato = :tipo WHERE id = :id"),
            {"tipo": tipo, "id": attribute.id.hex},
        )
        session.flush()
    session.rollback()


def test_database_rejects_missing_unit_foreign_key(session):
    session.add(Atributo(nombre="RAM", tipo_dato=TipoDato.INTEGER, unidad_id=uuid4()))
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        session.flush()
    session.rollback()


@pytest.mark.parametrize("legacy", [False, True])
def test_rename_and_undo_keep_code_and_legacy_snapshots_unchanged(session, legacy):
    service = AtributoService()
    attribute = service.create(session, {"nombre": "RAM", "tipo_dato": TipoDato.INTEGER})
    payload = {"nombre": "Memoria instalada"}
    service.update(session, attribute.id, payload)
    assert payload == {"nombre": "Memoria instalada"}
    snapshot = session.exec(select(AtributoCambio)).one()
    if legacy:
        for field in ("definicion_anterior", "definicion_posterior"):
            setattr(
                snapshot, field,
                {key: value for key, value in getattr(snapshot, field).items()
                 if key not in {"codigo", "unidad_id"}},
            )
        session.commit()
    else:
        assert snapshot.definicion_anterior["codigo"] == "ram"
        assert snapshot.definicion_posterior["unidad_id"] is None
    previous_definition = dict(snapshot.definicion_anterior)
    assert service.lifecycle_status(session, attribute.id)["can_undo"] is True
    service.undo(session, attribute.id)
    session.refresh(attribute)
    session.refresh(snapshot)
    assert attribute.nombre == "RAM"
    assert attribute.codigo == "ram"
    assert snapshot.definicion_anterior == previous_definition


def test_legacy_snapshot_does_not_allow_ambiguous_unit_restore(session, units):
    service = AtributoService()
    attribute = service.create(session, {"nombre": "RAM", "tipo_dato": TipoDato.INTEGER})
    service.update(session, attribute.id, {"nombre": "Memoria instalada"})
    snapshot = session.exec(select(AtributoCambio)).one()
    snapshot.definicion_posterior = {
        key: value for key, value in snapshot.definicion_posterior.items()
        if key not in {"codigo", "unidad_id"}
    }
    attribute.unidad_id = units[0].id
    session.add(attribute)
    session.add(snapshot)
    session.commit()
    assert service.lifecycle_status(session, attribute.id)["can_undo"] is False
    with pytest.raises(HTTPException) as error:
        service.undo(session, attribute.id)
    assert error.value.detail["code"] == "ATTRIBUTE_STATE_CHANGED"
    session.refresh(attribute)
    assert attribute.unidad_id == units[0].id
    assert attribute.nombre == "Memoria instalada"


def test_preview_includes_stable_code_and_serialized_unit_without_writes(session, units):
    service = AtributoService()
    attribute = service.create(session, {"nombre": "RAM", "tipo_dato": TipoDato.INTEGER})
    preview = service.preview_update(session, attribute.id, {"unidad_id": units[0].id})
    assert preview["definicion_propuesta"]["codigo"] == "ram"
    assert preview["definicion_propuesta"]["unidad_id"] == str(units[0].id)
    assert attribute.unidad_id is None
    assert session.exec(select(AtributoCambio)).all() == []


@pytest.mark.parametrize("operation", ["add", "swap", "remove"])
def test_unit_change_without_values_or_history_is_allowed(session, units, operation):
    service = AtributoService()
    initial_unit = None if operation == "add" else units[0].id
    target_unit = None if operation == "remove" else units[1].id
    attribute = service.create(
        session, {"nombre": "RAM", "tipo_dato": TipoDato.INTEGER, "unidad_id": initial_unit}
    )
    service.update(session, attribute.id, {"unidad_id": target_unit})
    assert attribute.unidad_id == target_unit
    snapshot = session.exec(select(AtributoCambio)).one()
    assert snapshot.definicion_anterior["unidad_id"] == (
        str(initial_unit) if initial_unit else None
    )
    service.undo(session, attribute.id)
    session.refresh(attribute)
    assert attribute.unidad_id == initial_unit
    assert attribute.codigo == "ram"


@pytest.mark.parametrize("active", [False, True])
@pytest.mark.parametrize(
    ("operation", "expected_code"),
    [
        ("add", "ATTRIBUTE_UNIT_ANNOTATION_REQUIRES_CONFIRMATION"),
        ("swap", "ATTRIBUTE_UNIT_CHANGE_REQUIRES_CONVERSION"),
        ("remove", "ATTRIBUTE_UNIT_REMOVAL_REQUIRES_MIGRATION"),
    ],
)
def test_unit_changes_with_values_remain_gated(session, units, active, operation, expected_code):
    service = AtributoService()
    initial_unit = None if operation == "add" else units[0].id
    target_unit = None if operation == "remove" else units[1].id
    attribute = service.create(
        session, {"nombre": "RAM", "tipo_dato": TipoDato.DECIMAL, "unidad_id": initial_unit}
    )
    product = Producto(nombre="Equipo")
    session.add(product)
    session.flush()
    value = ProductoAtributoValor(
        atributo_id=attribute.id, producto_id=product.id,
        valor_decimal=Decimal("16.125"), activo=active,
    )
    session.add(value)
    session.commit()
    for method in (service.preview_update, service.update):
        with pytest.raises(HTTPException) as error:
            method(session, attribute.id, {"unidad_id": target_unit})
        assert error.value.status_code == 409
        assert error.value.detail["code"] == expected_code
    session.refresh(attribute)
    session.refresh(value)
    assert attribute.unidad_id == initial_unit
    assert value.valor_decimal == Decimal("16.125")
    assert value.activo is active
    assert session.exec(select(AtributoCambio)).all() == []


def test_reverted_unit_snapshot_alone_blocks_unit_change(session, units):
    service = AtributoService()
    attribute = service.create(session, {"nombre": "RAM", "tipo_dato": TipoDato.INTEGER})
    service.update(session, attribute.id, {"unidad_id": units[0].id})
    service.undo(session, attribute.id)
    with pytest.raises(HTTPException) as error:
        service.update(session, attribute.id, {"unidad_id": units[1].id})
    assert error.value.detail["code"] == "ATTRIBUTE_UNIT_ANNOTATION_REQUIRES_CONFIRMATION"


def test_category_create_does_not_mutate_input(session):
    category = Categoria(nombre="Equipos")
    session.add(category)
    session.commit()
    payload = {"nombre": "RAM", "tipo_dato": TipoDato.INTEGER, "categoria_id": category.id}
    attribute = AtributoService().create_for_category(session, payload)
    assert payload == {
        "nombre": "RAM", "tipo_dato": TipoDato.INTEGER, "categoria_id": category.id
    }
    assert attribute.codigo == "ram"