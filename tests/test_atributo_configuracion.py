from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select
from uuid import UUID

from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.catalogo.entity import Catalogo, CatalogoValor
from osiris.modules.common.catalogo.service import CatalogoService
from osiris.core.db import get_session
from osiris.modules.inventario.atributo.entity import Atributo, TipoDato
from osiris.modules.inventario.atributo.models import AtributoCreate
from osiris.modules.inventario.atributo.router import router as atributo_router
from osiris.modules.inventario.atributo.service import AtributoService
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo


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
            CategoriaAtributo.__table__,
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
    app.dependency_overrides[post_route.dependant.dependencies[0].call] = lambda: None

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


def test_create_catalog_attribute_with_category_creates_catalog_and_assignment():
    engine = _engine()
    with Session(engine) as session:
        category = Categoria(nombre="Tecnología", es_padre=True, usuario_auditoria="test", activo=True)
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
            select(CategoriaAtributo).where(CategoriaAtributo.atributo_id == attribute.id)
        ).one()
        catalog = session.get(Catalogo, attribute.catalog_id)
        assert assignment.categoria_id == category.id
        assert catalog is not None
        assert catalog.nombre == "Marcas"


def test_create_attribute_rejects_duplicate_name_in_another_category():
    engine = _engine()
    with Session(engine) as session:
        first_category = Categoria(nombre="Mouse", es_padre=False, usuario_auditoria="test", activo=True)
        second_category = Categoria(nombre="Teclados", es_padre=False, usuario_auditoria="test", activo=True)
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
