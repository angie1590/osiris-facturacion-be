from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine, select

from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.catalogo.entity import Catalogo, CatalogoValor
from osiris.modules.common.catalogo.service import CatalogoService
from osiris.modules.inventario.atributo.entity import Atributo, TipoDato
from osiris.modules.inventario.atributo.models import AtributoCreate
from osiris.modules.inventario.atributo.service import AtributoService


def _engine():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(
        engine,
        tables=[AuditLog.__table__, Catalogo.__table__, CatalogoValor.__table__, Atributo.__table__],
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
