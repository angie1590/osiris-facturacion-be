from __future__ import annotations

import pytest
from decimal import Decimal
from types import SimpleNamespace
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select
from uuid import UUID, uuid4

from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.catalogo.entity import Catalogo, CatalogoValor
from osiris.modules.common.catalogo.service import CatalogoService
from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION, get_session
from osiris.modules.inventario.atributo.entity import Atributo, AtributoCambio, TipoDato
from osiris.modules.inventario.atributo.models import AtributoCreate
from osiris.modules.inventario.atributo.router import router as atributo_router
from osiris.modules.inventario.atributo.router import list_atributos
from osiris.modules.inventario.atributo.router import read_attributes_permission
from osiris.modules.inventario.atributo.router import create_and_assign_attribute_permission
from osiris.modules.inventario.atributo.router import deactivate_attribute_permission
from osiris.modules.inventario.atributo.router import preview_attribute_deactivation_permission
from osiris.modules.inventario.atributo.router import preview_attribute_update_permission
from osiris.modules.inventario.atributo.router import undo_attribute_change_permission
from osiris.modules.inventario.atributo.router import update_attribute_permission
from osiris.modules.inventario.atributo.service import AtributoService
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria.service import CategoriaService
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.common.unidad.entity import Unidad
from osiris.modules.inventario.producto.entity import Producto, ProductoCategoria, TipoProducto
from osiris.modules.inventario.producto.models_atributos import (
    ProductoAtributoRemapeo,
    ProductoAtributoValor,
)


def _engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(
        engine,
        tables=[
            AuditLog.__table__,
            Catalogo.__table__,
            CatalogoValor.__table__,
            Categoria.__table__,
            Atributo.__table__,
            AtributoCambio.__table__,
            CategoriaAtributo.__table__,
            Unidad.__table__,
            CasaComercial.__table__,
            Producto.__table__,
            ProductoCategoria.__table__,
            ProductoAtributoValor.__table__,
            ProductoAtributoRemapeo.__table__,
        ],
    )
    return engine

def test_select_attribute_requires_distinct_options():
    engine = _engine()
    with Session(engine) as session:
        service = AtributoService()
        created = service.create(
            session,
            AtributoCreate(
                nombre="Color",
                tipo_dato=TipoDato.SELECT,
                select_options=["Rojo", "Azul"],
            ),
        )
        assert created.select_options == ["Rojo", "Azul"]
        assert created.catalog_id is None

        with pytest.raises(HTTPException, match="Las opciones del atributo no pueden repetirse"):
            service.create(
                session,
                AtributoCreate(
                    nombre="Talla",
                    tipo_dato=TipoDato.SELECT,
                    select_options=["S", " s "],
                ),
            )


def test_catalog_attribute_creates_and_reuses_plural_catalog():
    engine = _engine()
    with Session(engine) as session:
        service = AtributoService()
        brand = service.create(
            session,
            AtributoCreate(nombre="Marca", tipo_dato=TipoDato.CATALOG),
        )
        catalog = session.get(Catalogo, brand.catalog_id)
        assert catalog is not None
        assert catalog.nombre == "Marcas"

        material = service.create(
            session,
            AtributoCreate(
                nombre="Material",
                tipo_dato=TipoDato.CATALOG,
                catalog_id=brand.catalog_id,
            ),
        )
        assert material.catalog_id == brand.catalog_id
        assert len(session.exec(select(Catalogo)).all()) == 1


def test_generic_catalog_values_can_be_reactivated():
    engine = _engine()
    service = CatalogoService()
    with Session(engine) as session:
        catalog = service.create(session, name="Colores")
        value = service.add_value(session, catalog["id"], "Rojo")
        assert value["value"] == "Rojo"

        service.toggle_value(session, catalog["id"], value["id"], active=False)
        reactivated = service.add_value(session, catalog["id"], "rojo")

        assert reactivated["is_active"] is True
        assert reactivated["value"] == "rojo"
        assert len(service.list_values(session, catalog["id"], include_inactive=True)) == 1


def test_create_attribute_requires_and_persists_category_assignment_atomically():
    engine = _engine()
    with Session(engine) as session:
        category = Categoria(nombre="Calzado", es_padre=True, usuario_auditoria="test", activo=True)
        session.add(category)
        session.commit()

        attribute = AtributoService().create_for_category(
            session,
            {
                "nombre": "Talla",
                "tipo_dato": TipoDato.STRING,
                "categoria_id": category.id,
                "usuario_auditoria": "test",
            },
        )

        assignment = session.exec(
            select(CategoriaAtributo).where(CategoriaAtributo.atributo_id == attribute.id)
        ).one()
        assert assignment.categoria_id == category.id
        assert assignment.activo is True


def test_post_attribute_endpoint_does_not_return_success_without_category_assignment():
    engine = _engine()
    app = FastAPI()
    app.include_router(atributo_router)

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    post_route = next(
        route
        for route in atributo_router.routes
        if getattr(route, "path", None) == "/api/v1/atributos"
        and "POST" in getattr(route, "methods", set())
    )
    app.dependency_overrides[post_route.dependant.dependencies[0].call] = lambda: SimpleNamespace(
        id="actor-test"
    )

    with Session(engine) as session:
        category = Categoria(nombre="Mouse", es_padre=False, usuario_auditoria="test", activo=True)
        session.add(category)
        session.commit()
        category_id = category.id

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/atributos",
            json={
                "nombre": "Conectividad",
                "tipo_dato": "select",
                "select_options": ["Bluetooth"],
                "categoria_id": str(category_id),
                "usuario_auditoria": "test",
            },
        )

    assert response.status_code == 201, response.text
    with Session(engine) as session:
        attribute = session.exec(
            select(Atributo).where(Atributo.id == UUID(response.json()["id"]))
        ).one()
        assignment = session.exec(
            select(CategoriaAtributo).where(CategoriaAtributo.atributo_id == attribute.id)
        ).one()
        assert assignment.categoria_id == category_id


def test_new_required_attribute_preview_is_read_only_and_backfill_is_atomic():
    engine = _engine()
    app = FastAPI()
    app.include_router(atributo_router)
    actor = SimpleNamespace(id=uuid4())

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[create_and_assign_attribute_permission] = lambda: actor
    with Session(engine) as session:
        category = Categoria(nombre="Televisores", activo=True)
        product = Producto(
            nombre="Televisor pendiente",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("20.00"),
            activo=True,
        )
        session.add_all([category, product])
        session.flush()
        session.add(
            ProductoCategoria(producto_id=product.id, categoria_id=category.id)
        )
        session.commit()
        session.refresh(category)
        session.refresh(product)
        category_id = category.id
        product_id = product.id
        client = TestClient(app)
        payload = {
            "categoria_id": str(category_id),
            "nombre": "Tecnología de panel",
            "tipo_dato": "string",
            "obligatorio": True,
            "valor_default": None,
            "aplicar_default_a_existentes": False,
        }

        preview = client.post("/api/v1/atributos/previsualizar", json=payload)
        assert preview.status_code == 200, preview.text
        assert preview.json()["conteos"]["productos_afectados"] == 1
        assert preview.json()["conteos"]["productos_faltantes"] == 1
        assert preview.json()["faltantes"][0]["id"] == str(product_id)
        assert session.exec(select(Atributo)).all() == []

        blocked = client.post(
            "/api/v1/atributos",
            json={
                **payload,
                "precondicion_preview": preview.json()["precondicion_preview"],
            },
        )
        assert blocked.status_code == 409
        assert blocked.json()["detail"]["code"] == "PRODUCT_REQUIRED_ATTRIBUTES_MISSING"
        assert session.exec(select(Atributo)).all() == []
        assert session.exec(select(CategoriaAtributo)).all() == []

        confirmed_payload = {
            **payload,
            "valor_default": "IPS",
            "aplicar_default_a_existentes": True,
        }
        confirmed_preview = client.post(
            "/api/v1/atributos/previsualizar", json=confirmed_payload
        )
        assert confirmed_preview.status_code == 200, confirmed_preview.text
        created = client.post(
            "/api/v1/atributos",
            json={
                **confirmed_payload,
                "precondicion_preview": confirmed_preview.json()["precondicion_preview"],
            },
        )
        assert created.status_code == 201, created.text
        with Session(engine) as session:
            attribute_id = UUID(created.json()["id"])
            mapping = session.exec(
                select(CategoriaAtributo).where(
                    CategoriaAtributo.atributo_id == attribute_id
                )
            ).one()
            value = session.exec(
                select(ProductoAtributoValor).where(
                    ProductoAtributoValor.producto_id == product_id,
                    ProductoAtributoValor.atributo_id == attribute_id,
                )
            ).one()
            assert mapping.categoria_id == category_id
            assert value.valor_string == "IPS"

def test_create_attribute_rejects_duplicate_name_in_another_category():
    engine = _engine()
    with Session(engine) as session:
        first_category = Categoria(
            nombre="Mouse", es_padre=False, usuario_auditoria="test", activo=True
        )
        second_category = Categoria(
            nombre="Teclados", es_padre=False, usuario_auditoria="test", activo=True
        )
        session.add_all([first_category, second_category])
        session.commit()

        service = AtributoService()
        service.create_for_category(
            session,
            {
                "nombre": "DPI",
                "tipo_dato": TipoDato.INTEGER,
                "categoria_id": first_category.id,
                "usuario_auditoria": "test",
            },
        )

        with pytest.raises(HTTPException, match="Ya existe un atributo activo") as exc_info:
            service.create_for_category(
                session,
                {
                    "nombre": " dpi ",
                    "tipo_dato": TipoDato.STRING,
                    "categoria_id": second_category.id,
                    "usuario_auditoria": "test",
                },
            )

        assert exc_info.value.status_code == 409
        assert len(session.exec(select(Atributo)).all()) == 1


def test_create_attribute_rolls_back_when_category_does_not_exist():
    engine = _engine()
    with Session(engine) as session:
        with pytest.raises(HTTPException, match="Categoría no encontrada"):
            AtributoService().create_for_category(
                session,
                {
                    "nombre": "Talla",
                    "tipo_dato": TipoDato.STRING,
                    "categoria_id": "00000000-0000-0000-0000-000000000001",
                    "usuario_auditoria": "test",
                },
            )

        assert session.exec(select(Atributo)).all() == []


def test_attribute_list_includes_unit_summary():
    engine = _engine()
    with Session(engine) as session:
        unit = Unidad(
            codigo="centimetro",
            nombre="Centímetro",
            simbolo="cm",
            magnitud_codigo="longitud",
            usuario_auditoria="test",
        )
        session.add(unit)
        session.commit()
        session.refresh(unit)
        session.add(
            Atributo(
                nombre="Largo",
                codigo="largo",
                tipo_dato=TipoDato.DECIMAL,
                unidad_id=unit.id,
                usuario_auditoria="test",
            )
        )
        session.commit()

        response = list_atributos(
            limit=50, offset=0, only_active=True, session=session
        )

    assert response.items[0].unidad is not None
    assert response.items[0].unidad.nombre == "Centímetro"
    assert response.items[0].unidad.simbolo == "cm"


def test_attribute_deactivation_requires_signed_preview_and_deactivates_atomically():
    engine = _engine()
    app = FastAPI()
    app.include_router(atributo_router)
    actor = SimpleNamespace(id=uuid4())

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[deactivate_attribute_permission] = lambda: actor
    app.dependency_overrides[preview_attribute_deactivation_permission] = lambda: actor
    with Session(engine) as session:
        category = Categoria(nombre="Accesorios", activo=True)
        attribute = Atributo(
            nombre="Conector", tipo_dato=TipoDato.STRING, activo=True
        )
        product = Producto(
            nombre="Audífonos",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("12.00"),
            cantidad=Decimal("5.0000"),
            activo=True,
        )
        session.add_all([category, attribute, product])
        session.flush()
        mapping = CategoriaAtributo(
            categoria_id=category.id,
            atributo_id=attribute.id,
            obligatorio=False,
            activo=True,
        )
        value = ProductoAtributoValor(
            producto_id=product.id,
            atributo_id=attribute.id,
            valor_string="USB-C",
            activo=True,
        )
        session.add_all(
            [
                mapping,
                value,
                ProductoCategoria(producto_id=product.id, categoria_id=category.id),
            ]
        )
        session.commit()
        attribute_id = attribute.id
        category_id = category.id
        product_id = product.id
        mapping_id = mapping.id
        value_id = value.id
    written_statements: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def capture_writes(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().split(maxsplit=1)[0].upper() in {"INSERT", "UPDATE", "DELETE"}:
            written_statements.append(statement.upper())

    with TestClient(app) as client:
        preview = client.post(f"/api/v1/atributos/{attribute_id}/previsualizar-baja")
        assert preview.status_code == 200, preview.text
        assert preview.json()["conteos"]["asignaciones_activas"] == 1
        assert preview.json()["conteos"]["valores_activos"] == 1
        assert preview.json()["precondicion_preview"]
        missing_token = client.request(
            "DELETE",
            f"/api/v1/atributos/{attribute_id}",
            json={"payload": {"confirmar": True}, "precondicion_preview": "invalid-preview"},
        )
        assert missing_token.status_code == 409
        assert missing_token.json()["detail"]["code"] == "CATALOG_PREVIEW_STALE"
        response = client.request(
            "DELETE",
            f"/api/v1/atributos/{attribute_id}",
            json={
                "payload": {"confirmar": True},
                "precondicion_preview": preview.json()["precondicion_preview"],
            },
        )
        assert response.status_code == 204, response.text

    with Session(engine) as session:
        assert session.exec(
            select(Atributo)
            .where(Atributo.id == attribute_id)
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        ).one().activo is False
        assert session.exec(
            select(CategoriaAtributo)
            .where(CategoriaAtributo.id == mapping_id)
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        ).one().activo is False
        assert session.exec(
            select(ProductoAtributoValor)
            .where(ProductoAtributoValor.id == value_id)
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        ).one().activo is False
        current_product = session.get(Producto, product_id)
        assert current_product is not None
        assert current_product.activo is True
        assert current_product.cantidad == Decimal("5.0000")
        assert session.exec(
            select(ProductoCategoria).where(
                ProductoCategoria.producto_id == product_id
            )
        ).one().categoria_id == category_id
        assert not any(
            table in statement
            for statement in written_statements
            for table in (
                "TBL_PRODUCTO_BODEGA",
                "TBL_PRODUCTO_IMPUESTO",
                "TBL_VENTA",
                "TBL_VENTA_DETALLE",
                "TBL_COMPRA",
                "TBL_COMPRA_DETALLE",
                "TBL_MOVIMIENTO_INVENTARIO",
            )
        )


def test_create_catalog_attribute_with_category_creates_catalog_and_assignment():
    engine = _engine()
    with Session(engine) as session:
        category = Categoria(
            nombre="Tecnología", es_padre=True, usuario_auditoria="test", activo=True
        )
        session.add(category)
        session.commit()

        attribute = AtributoService().create_for_category(
            session,
            {
                "nombre": "Marca",
                "tipo_dato": TipoDato.CATALOG,
                "categoria_id": category.id,
                "usuario_auditoria": "test",
            },
        )

        assignment = session.exec(
            select(CategoriaAtributo).where(
                CategoriaAtributo.atributo_id == attribute.id
            )
        ).one()
        catalog = session.get(Catalogo, attribute.catalog_id)
        assert assignment.categoria_id == category.id
        assert catalog is not None
        assert catalog.nombre == "Marcas"


def test_unit_annotation_preview_is_signed_and_preserves_values_and_defaults(monkeypatch):
    engine = _engine()
    app = FastAPI()
    app.include_router(atributo_router)
    actor = SimpleNamespace(id=uuid4())
    monkeypatch.setattr(
        CategoriaService,
        "acquire_hierarchy_mutation_lock",
        staticmethod(lambda _session: None),
    )

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[preview_attribute_update_permission] = lambda: actor
    app.dependency_overrides[update_attribute_permission] = lambda: actor
    with Session(engine) as session:
        unit = Unidad(
            codigo="GIGABYTE",
            nombre="Gigabyte",
            simbolo="GB",
            magnitud_codigo="DATA_STORAGE",
        )
        category = Categoria(nombre="Computadores", activo=True)
        attribute = Atributo(nombre="Memoria RAM", tipo_dato=TipoDato.DECIMAL)
        product = Producto(
            nombre="Equipo test",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("20.00"),
            activo=True,
        )
        session.add_all([unit, category, attribute, product])
        session.flush()
        assignment = CategoriaAtributo(
            categoria_id=category.id,
            atributo_id=attribute.id,
            valor_default="16.125",
            obligatorio=False,
            activo=True,
        )
        value = ProductoAtributoValor(
            producto_id=product.id,
            atributo_id=attribute.id,
            valor_decimal=Decimal("16.125"),
            activo=True,
        )
        session.add_all([assignment, value])
        session.flush()
        session.add(
            AtributoCambio(
                atributo_id=attribute.id,
                operacion="update",
                definicion_anterior={"codigo": "memoria_ram", "unidad_id": None},
                definicion_posterior={"codigo": "memoria_ram", "unidad_id": None},
                asignaciones_anteriores=[
                    {"id": str(assignment.id), "valor_default": "16.125"}
                ],
                asignaciones_posteriores=[],
                valores_anteriores=[
                    {
                        "id": str(value.id),
                        "producto_id": str(product.id),
                        "valor_decimal": "16.125",
                        "activo": True,
                    }
                ],
                valores_posteriores=[],
                remapeos_anteriores=[],
                remapeos_posteriores=[],
            )
        )
        session.commit()
        unit_id = unit.id
        attribute_id = attribute.id
        value_id = value.id
        assignment_id = assignment.id

    with TestClient(app) as client:
        preview_response = client.post(
            f"/api/v1/atributos/{attribute_id}/previsualizar",
            json={"unidad_id": str(unit_id)},
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview["requiere_confirmacion"] is True
        assert preview["unidad_anotacion"]["unidad"] == {
            "id": str(unit_id),
            "nombre": "Gigabyte",
            "simbolo": "GB",
        }
        assert preview["unidad_anotacion"]["conteos"] == {
            "valores_activos": 1,
            "valores_inactivos": 0,
            "valores_historicos": 1,
            "defaults_actuales": 1,
            "defaults_historicos": 1,
            "productos_afectados": 1,
        }
        assert preview["convertibles"] == 0
        with Session(engine) as session:
            assert session.get(Atributo, attribute_id).unidad_id is None
            assert len(session.exec(select(AtributoCambio)).all()) == 1

        missing_consent = client.put(
            f"/api/v1/atributos/{attribute_id}",
            json={"unidad_id": str(unit_id)},
        )
        assert missing_consent.status_code == 409
        assert missing_consent.json()["detail"]["code"] == (
            "ATTRIBUTE_UNIT_ANNOTATION_REQUIRES_CONFIRMATION"
        )

        with Session(engine) as session:
            stored_value = session.get(ProductoAtributoValor, value_id)
            stored_value.valor_decimal = Decimal("17.250")
            session.add(stored_value)
            session.commit()
        stale = client.put(
            f"/api/v1/atributos/{attribute_id}",
            json={
                "unidad_id": str(unit_id),
                "confirmar_anotacion_unidad": True,
                "precondicion_preview": preview["precondicion_preview"],
            },
        )
        assert stale.status_code == 409
        assert stale.json()["detail"]["code"] == "CATALOG_PREVIEW_STALE"

        refreshed_preview = client.post(
            f"/api/v1/atributos/{attribute_id}/previsualizar",
            json={"unidad_id": str(unit_id)},
        )
        with Session(engine) as session:
            changed_unit = session.exec(
                select(Unidad)
                .where(Unidad.id == unit_id)
                .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
            ).one()
            changed_unit.activo = False
            session.add(changed_unit)
            session.commit()
        inactive_unit = client.put(
            f"/api/v1/atributos/{attribute_id}",
            json={
                "unidad_id": str(unit_id),
                "confirmar_anotacion_unidad": True,
                "precondicion_preview": refreshed_preview.json()["precondicion_preview"],
            },
        )
        assert inactive_unit.status_code == 409
        assert inactive_unit.json()["detail"]["code"] == "CATALOG_PREVIEW_STALE"
        with Session(engine) as session:
            changed_unit = session.exec(
                select(Unidad)
                .where(Unidad.id == unit_id)
                .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
            ).one()
            changed_unit.activo = True
            session.add(changed_unit)
            session.commit()
        refreshed_preview = client.post(
            f"/api/v1/atributos/{attribute_id}/previsualizar",
            json={"unidad_id": str(unit_id)},
        )
        confirmed = client.put(
            f"/api/v1/atributos/{attribute_id}",
            json={
                "unidad_id": str(unit_id),
                "confirmar_anotacion_unidad": True,
                "precondicion_preview": refreshed_preview.json()["precondicion_preview"],
            },
        )
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["unidad_id"] == str(unit_id)
        assert confirmed.json()["unidad"]["simbolo"] == "GB"
        with Session(engine) as session:
            stored_attribute = session.get(Atributo, attribute_id)
            stored_value = session.get(ProductoAtributoValor, value_id)
            stored_assignment = session.get(CategoriaAtributo, assignment_id)
            snapshots = session.exec(select(AtributoCambio)).all()
            assert stored_attribute.unidad_id == unit_id
            assert stored_value.valor_decimal == Decimal("17.250")
            assert stored_assignment.valor_default == "16.125"
            assert snapshots[-1].operacion == "annotate_unit"
            assert snapshots[-1].definicion_anterior["unidad_id"] is None
            assert snapshots[-1].definicion_posterior["unidad_id"] == str(unit_id)
            assert any(
                audit.accion == "ANNOTATE_ATTRIBUTE_UNIT"
                for audit in session.exec(select(AuditLog)).all()
            )




def test_attribute_unit_api_create_annotate_and_undo_preserves_numeric_state(monkeypatch):
    engine = _engine()
    app = FastAPI()
    app.include_router(atributo_router)
    actor = SimpleNamespace(id=uuid4())
    monkeypatch.setattr(
        CategoriaService,
        "acquire_hierarchy_mutation_lock",
        staticmethod(lambda _session: None),
    )

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[create_and_assign_attribute_permission] = lambda: actor
    app.dependency_overrides[preview_attribute_update_permission] = lambda: actor
    app.dependency_overrides[update_attribute_permission] = lambda: actor
    app.dependency_overrides[read_attributes_permission] = lambda: actor
    app.dependency_overrides[undo_attribute_change_permission] = lambda: actor
    with Session(engine) as session:
        category = Categoria(nombre="Computadores", activo=True)
        unit = Unidad(
            codigo="GIGABYTE",
            nombre="Gigabyte",
            simbolo="GB",
            magnitud_codigo="DATA_STORAGE",
        )
        product = Producto(
            nombre="Equipo E2E",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("20.00"),
            activo=True,
        )
        session.add_all([category, unit, product])
        session.flush()
        session.add(ProductoCategoria(producto_id=product.id, categoria_id=category.id))
        session.commit()
        category_id = category.id
        unit_id = unit.id
        product_id = product.id

    with TestClient(app) as client:
        no_unit = client.post(
            "/api/v1/atributos",
            json={
                "categoria_id": str(category_id),
                "nombre": "Capacidad sin unidad",
                "tipo_dato": "decimal",
                "valor_default": "1.5",
                "aplicar_default_a_existentes": False,
            },
        )
        assert no_unit.status_code == 201, no_unit.text
        assert no_unit.json()["unidad_id"] is None
        no_unit_id = UUID(no_unit.json()["id"])

        with_unit = client.post(
            "/api/v1/atributos",
            json={
                "categoria_id": str(category_id),
                "nombre": "Ancho con unidad",
                "tipo_dato": "decimal",
                "unidad_id": str(unit_id),
                "aplicar_default_a_existentes": False,
            },
        )
        assert with_unit.status_code == 201, with_unit.text
        assert with_unit.json()["unidad_id"] == str(unit_id)
        assert with_unit.json()["unidad"]["simbolo"] == "GB"

        with Session(engine) as session:
            value = ProductoAtributoValor(
                producto_id=product_id,
                atributo_id=no_unit_id,
                valor_decimal=Decimal("17.250"),
                activo=True,
            )
            session.add(value)
            session.commit()

        preview = client.post(
            f"/api/v1/atributos/{no_unit_id}/previsualizar",
            json={"unidad_id": str(unit_id)},
        )
        assert preview.status_code == 200, preview.text
        assert preview.json()["unidad_anotacion"]["conteos"]["valores_activos"] == 1
        confirmed = client.put(
            f"/api/v1/atributos/{no_unit_id}",
            json={
                "unidad_id": str(unit_id),
                "confirmar_anotacion_unidad": True,
                "precondicion_preview": preview.json()["precondicion_preview"],
            },
        )
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["unidad"]["simbolo"] == "GB"

        lifecycle = client.get(f"/api/v1/atributos/{no_unit_id}/reversion")
        assert lifecycle.status_code == 200
        assert lifecycle.json()["operacion"] == "annotate_unit"
        assert lifecycle.json()["can_undo"] is True
        undone = client.post(f"/api/v1/atributos/{no_unit_id}/revertir")
        assert undone.status_code == 200, undone.text

    with Session(engine) as session:
        annotated = session.get(Atributo, no_unit_id)
        value = session.exec(
            select(ProductoAtributoValor).where(
                ProductoAtributoValor.atributo_id == no_unit_id
            )
        ).one()
        mapping = session.exec(
            select(CategoriaAtributo).where(
                CategoriaAtributo.atributo_id == no_unit_id
            )
        ).one()
        assert annotated.unidad_id is None
        assert value.valor_decimal == Decimal("17.250")
        assert mapping.valor_default == "1.5"
