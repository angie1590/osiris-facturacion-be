from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic
from uuid import uuid4
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy.engine import Engine
from osiris.core.audit import record_domain_change
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from osiris.core.audit_context import reset_current_company_id, set_current_company_id
from osiris.core.catalog_lock import CATALOG_MUTATION_LOCK_KEY
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.catalogo.entity import Catalogo
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.common.tipo_cliente.entity import TipoCliente
from osiris.modules.common.unidad.entity import Unidad
from osiris.modules.inventario.atributo.entity import Atributo, TipoDato
from osiris.modules.inventario.bodega.entity import Bodega
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria.service import CategoriaService
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.inventario.producto.entity import (
    Producto,
    ProductoBodega,
    ProductoCategoria,
    ProductoImpuesto,
    TipoProducto,
)
from osiris.modules.inventario.producto.models import ProductoIntegralCreate
from osiris.modules.inventario.producto.models_atributos import ProductoAtributoValor
from osiris.modules.inventario.producto.service import ProductoService
from osiris.modules.inventario.producto.router import router as producto_router
from osiris.modules.inventario.producto.category_preview import (
    OPERATION,
    preview_product_category_change,
    product_category_preview_payload,
    product_category_preview_state,
    product_preview_signer,
)
from osiris.modules.inventario.producto.models import ProductoIntegralUpdate
from osiris.modules.inventario.producto.models import (
    ProductoCambioCategoriaPreviewInput,
)
from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION, get_session
from osiris.core.product_permissions import update_product_permission
from osiris.modules.sri.impuesto_catalogo.entity import (
    AplicaA,
    ClasificacionIVA,
    ImpuestoCatalogo,
    TipoImpuesto,
)
from osiris.modules.sri.tipo_contribuyente.entity import TipoContribuyente


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
            Empresa.__table__,
            Sucursal.__table__,
            TipoCliente.__table__,
            TipoContribuyente.__table__,
            Unidad.__table__,
            CasaComercial.__table__,
            Categoria.__table__,
            CategoriaAtributo.__table__,
            Atributo.__table__,
            Producto.__table__,
            Bodega.__table__,
            ProductoBodega.__table__,
            ProductoCategoria.__table__,
            ProductoAtributoValor.__table__,
            ImpuestoCatalogo.__table__,
            ProductoImpuesto.__table__,
        ],
    )
    return engine


@pytest.fixture
def postgresql_product_engine() -> Iterator[Engine]:
    value = os.environ.get("CATALOG_TEST_DATABASE_URL")
    if not value:
        pytest.skip("PostgreSQL opt-in: CATALOG_TEST_DATABASE_URL is not configured")
    url = sa.engine.make_url(value)
    if url.get_backend_name() != "postgresql":
        pytest.fail("CATALOG_TEST_DATABASE_URL must point to PostgreSQL")
    admin = sa.create_engine(
        url.set(drivername="postgresql+psycopg"),
        hide_parameters=True,
        connect_args={"connect_timeout": 5},
    )
    schema = "product_category_test_" + uuid4().hex
    with admin.begin() as connection:
        connection.execute(sa.schema.CreateSchema(schema))
    engine = admin.execution_options(schema_translate_map={None: schema})
    try:
        SQLModel.metadata.create_all(
            engine,
            tables=[
                AuditLog.__table__,
                Catalogo.__table__,
                Empresa.__table__,
                Sucursal.__table__,
                TipoCliente.__table__,
                TipoContribuyente.__table__,
                Unidad.__table__,
                CasaComercial.__table__,
                Categoria.__table__,
                CategoriaAtributo.__table__,
                Atributo.__table__,
                Producto.__table__,
                Bodega.__table__,
                ProductoBodega.__table__,
                ProductoCategoria.__table__,
                ProductoAtributoValor.__table__,
                ImpuestoCatalogo.__table__,
                ProductoImpuesto.__table__,
            ],
        )
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(sa.schema.DropSchema(schema, cascade=True))
        admin.dispose()


def _seed_catalog(session: Session, *, default_value: str | None):
    if session.get(TipoContribuyente, "01") is None:
        session.add(TipoContribuyente(codigo="01", nombre="Sociedad", activo=True))
        session.flush()
    company = Empresa(
        razon_social="Empresa de pruebas",
        ruc="1790012345001",
        direccion_matriz="Direccion de pruebas",
        regimen="GENERAL",
        modo_emision="ELECTRONICO",
        tipo_contribuyente_id="01",
        usuario_auditoria="fixture",
        activo=True,
    )
    category = Categoria(
        nombre="Mouse",
        es_padre=False,
        is_default=False,
        usuario_auditoria="fixture",
        activo=True,
    )
    attribute = Atributo(
        nombre="DPI",
        codigo=f"dpi_{uuid4().hex[:8]}",
        tipo_dato=TipoDato.INTEGER,
        usuario_auditoria="fixture",
        activo=True,
    )
    tax = ImpuestoCatalogo(
        tipo_impuesto=TipoImpuesto.IVA,
        codigo_tipo_impuesto="2",
        codigo_sri="0",
        descripcion=f"IVA 0 {uuid4().hex[:8]}",
        vigente_desde=date.today(),
        aplica_a=AplicaA.AMBOS,
        porcentaje_iva=Decimal("0"),
        usuario_auditoria="fixture",
        activo=True,
    )
    session.add_all([company, category, attribute, tax])
    session.flush()
    company.impuesto_catalogo_ids = [str(tax.id)]
    session.add(
        CategoriaAtributo(
            categoria_id=category.id,
            atributo_id=attribute.id,
            obligatorio=True,
            valor_default=default_value,
            usuario_auditoria="fixture",
            activo=True,
        )
    )
    session.commit()
    return company.id, category.id, attribute.id, tax.id


def _payload(category_id, tax_id) -> ProductoIntegralCreate:
    return ProductoIntegralCreate(
        nombre=f"Producto integral {uuid4().hex[:8]}",
        tipo=TipoProducto.BIEN,
        pvp=Decimal("10.00"),
        categoria_principal_id=category_id,
        impuesto_catalogo_ids=[tax_id],
    )


def test_create_integral_commits_product_category_tax_required_default_and_audit():
    engine = _engine()
    with Session(engine) as session:
        company_id, category_id, _attribute_id, tax_id = _seed_catalog(
            session, default_value="1600"
        )

    company_token = set_current_company_id(str(company_id))
    try:
        with Session(engine) as session:
            product = ProductoService().create_integral(
                session,
                _payload(category_id, tax_id),
                actor_id=uuid4(),
            )
            product_id = product.id
    finally:
        reset_current_company_id(company_token)

    with Session(engine) as session:
        product = session.get(Producto, product_id)
        assert product is not None
        assert product.categoria_principal_id == category_id
        assert session.exec(
            select(ProductoCategoria).where(
                ProductoCategoria.producto_id == product_id,
                ProductoCategoria.categoria_id == category_id,
            )
        ).first() is not None
        assert session.exec(
            select(ProductoImpuesto).where(
                ProductoImpuesto.producto_id == product_id,
                ProductoImpuesto.impuesto_catalogo_id == tax_id,
                ProductoImpuesto.activo.is_(True),
            )
        ).first() is not None
        attribute_value = session.exec(
            select(ProductoAtributoValor).where(
                ProductoAtributoValor.producto_id == product_id,
                ProductoAtributoValor.activo.is_(True),
            )
        ).one()
        assert attribute_value.valor_integer == 1600
        product_actions = set(
            session.exec(
                select(AuditLog.accion).where(
                    AuditLog.entidad_id == product_id,
                    AuditLog.accion != "UPSERT_PRODUCT_ATTRIBUTE_VALUE",
                )
            ).all()
        )
        assert {
            "CREATE_PRODUCT_INTEGRAL",
            "SET_PRODUCT_PRIMARY_CATEGORY",
            "CREATE_PRODUCT_TAX_PROFILE",
        } <= product_actions
        assert session.exec(
            select(AuditLog.id).where(AuditLog.accion == "UPSERT_PRODUCT_ATTRIBUTE_VALUE")
        ).first() is not None


def test_company_can_configure_multiple_iva_rates_for_different_products():
    engine = _engine()
    with Session(engine) as session:
        company_id, category_id, _attribute_id, iva_zero_id = _seed_catalog(
            session, default_value="1600"
        )
        iva_fifteen = ImpuestoCatalogo(
            tipo_impuesto=TipoImpuesto.IVA,
            codigo_tipo_impuesto="2",
            codigo_sri="4",
            descripcion="IVA 15% company multi-rate test",
            vigente_desde=date.today(),
            aplica_a=AplicaA.AMBOS,
            porcentaje_iva=Decimal("15.00"),
            clasificacion_iva=ClasificacionIVA.GRAVADO,
            usuario_auditoria="fixture",
            activo=True,
        )
        iva_exento = ImpuestoCatalogo(
            tipo_impuesto=TipoImpuesto.IVA,
            codigo_tipo_impuesto="2",
            codigo_sri="7",
            descripcion="IVA exento company multi-rate test",
            vigente_desde=date.today(),
            aplica_a=AplicaA.AMBOS,
            porcentaje_iva=Decimal("0.00"),
            clasificacion_iva=ClasificacionIVA.EXENTO,
            usuario_auditoria="fixture",
            activo=True,
        )
        session.add_all([iva_fifteen, iva_exento])
        session.flush()
        company = session.get(Empresa, company_id)
        assert company is not None
        company.impuesto_catalogo_ids = [
            str(iva_zero_id),
            str(iva_fifteen.id),
            str(iva_exento.id),
        ]
        session.add(company)
        session.commit()
        tax_ids = [iva_zero_id, iva_fifteen.id, iva_exento.id]

    company_token = set_current_company_id(str(company_id))
    try:
        product_ids = []
        for tax_id in tax_ids:
            with Session(engine) as session:
                product = ProductoService().create_integral(
                    session,
                    ProductoIntegralCreate(
                        nombre=f"Producto tarifa {tax_id.hex[:8]}",
                        tipo=TipoProducto.BIEN,
                        pvp=Decimal("10.00"),
                        categoria_principal_id=category_id,
                        impuesto_catalogo_ids=[tax_id],
                        atributos=[],
                    ),
                    actor_id=uuid4(),
                )
                product_ids.append(product.id)

        with Session(engine) as session:
            assigned_taxes = [
                session.exec(
                    select(ProductoImpuesto.impuesto_catalogo_id).where(
                        ProductoImpuesto.producto_id == product_id,
                        ProductoImpuesto.activo.is_(True),
                    )
                ).one()
                for product_id in product_ids
            ]
            assert assigned_taxes == tax_ids
    finally:
        reset_current_company_id(company_token)


def test_create_integral_rolls_back_product_bridge_tax_and_audit_when_required_missing():
    engine = _engine()
    with Session(engine) as session:
        company_id, category_id, _attribute_id, tax_id = _seed_catalog(session, default_value=None)
        audit_before = set(session.exec(select(AuditLog.id)).all())

    company_token = set_current_company_id(str(company_id))
    try:
        with Session(engine) as session:
            with pytest.raises(HTTPException) as error:
                ProductoService().create_integral(
                    session,
                    _payload(category_id, tax_id),
                    actor_id=uuid4(),
                )
            assert error.value.status_code == 422
            assert error.value.detail["code"] == "PRODUCT_REQUIRED_ATTRIBUTES_MISSING"
            assert not session.in_transaction()
    finally:
        reset_current_company_id(company_token)

    with Session(engine) as session:
        assert session.exec(select(Producto)).all() == []
        assert session.exec(select(ProductoCategoria)).all() == []
        assert session.exec(select(ProductoImpuesto)).all() == []
        assert session.exec(select(ProductoAtributoValor)).all() == []
        assert set(session.exec(select(AuditLog.id)).all()) == audit_before


def test_create_integral_rejects_non_applicable_attribute_before_persisting():
    engine = _engine()
    with Session(engine) as session:
        company_id, category_id, _attribute_id, tax_id = _seed_catalog(
            session, default_value="1600"
        )

    payload = ProductoIntegralCreate.model_validate(
        {
            **_payload(category_id, tax_id).model_dump(),
            "atributos": [{"atributo_id": str(uuid4()), "valor": "extra"}],
        }
    )
    company_token = set_current_company_id(str(company_id))
    try:
        with Session(engine) as session:
            with pytest.raises(HTTPException) as error:
                ProductoService().create_integral(session, payload, actor_id=uuid4())
            assert error.value.status_code == 422
            assert error.value.detail["code"] == "PRODUCT_ATTRIBUTE_NOT_APPLICABLE"
            assert not session.in_transaction()
    finally:
        reset_current_company_id(company_token)

    with Session(engine) as session:
        assert session.exec(select(Producto)).all() == []
        assert session.exec(select(ProductoCategoria)).all() == []
        assert session.exec(select(ProductoImpuesto)).all() == []
        assert session.exec(select(ProductoAtributoValor)).all() == []


def test_create_integral_rejects_unavailable_tax_profile_before_persisting():
    engine = _engine()
    with Session(engine) as session:
        company_id, category_id, _attribute_id, _tax_id = _seed_catalog(
            session, default_value="1600"
        )

    payload = _payload(category_id, uuid4())
    company_token = set_current_company_id(str(company_id))
    try:
        with Session(engine) as session:
            with pytest.raises(HTTPException) as error:
                ProductoService().create_integral(session, payload, actor_id=uuid4())
            assert error.value.status_code == 422
            assert error.value.detail["code"] == "PRODUCT_TAX_PROFILE_INVALID"
            assert not session.in_transaction()
    finally:
        reset_current_company_id(company_token)

    with Session(engine) as session:
        assert session.exec(select(Producto)).all() == []
        assert session.exec(select(ProductoCategoria)).all() == []
        assert session.exec(select(ProductoImpuesto)).all() == []
        assert session.exec(select(ProductoAtributoValor)).all() == []


def test_update_integral_preserves_attributes_when_collection_is_omitted():
    engine = _engine()
    with Session(engine) as session:
        company_id, category_id, _attribute_id, tax_id = _seed_catalog(
            session, default_value="1600"
        )
    company_token = set_current_company_id(str(company_id))
    try:
        with Session(engine) as session:
            product = ProductoService().create_integral(
                session, _payload(category_id, tax_id), actor_id=uuid4()
            )
            product_id = product.id
            updated = ProductoService().update_integral(
                session,
                product_id,
                ProductoIntegralUpdate(
                    categoria_principal_id=category_id,
                    nombre="Mouse renombrado",
                ),
                actor_id=uuid4(),
            )
            assert updated is not None
            assert updated.nombre == "Mouse renombrado"
    finally:
        reset_current_company_id(company_token)

    with Session(engine) as session:
        value = session.exec(
            select(ProductoAtributoValor).where(
                ProductoAtributoValor.producto_id == product_id,
                ProductoAtributoValor.activo.is_(True),
            )
        ).one()
        assert value.valor_integer == 1600


def test_update_integral_null_deactivates_only_optional_and_preserves_history():
    engine = _engine()
    with Session(engine) as session:
        company_id, category_id, required_attribute_id, tax_id = _seed_catalog(
            session, default_value="1600"
        )
        optional_attribute = Atributo(
            nombre="Inalambrico",
            codigo=f"inalambrico_{uuid4().hex[:8]}",
            tipo_dato=TipoDato.BOOLEAN,
            usuario_auditoria="fixture",
            activo=True,
        )
        session.add(optional_attribute)
        session.flush()
        session.add(
            CategoriaAtributo(
                categoria_id=category_id,
                atributo_id=optional_attribute.id,
                obligatorio=False,
                usuario_auditoria="fixture",
                activo=True,
            )
        )
        session.commit()
        optional_attribute_id = optional_attribute.id

    company_token = set_current_company_id(str(company_id))
    try:
        with Session(engine) as session:
            product = ProductoService().create_integral(
                session, _payload(category_id, tax_id), actor_id=uuid4()
            )
            product_id = product.id
            optional_value = ProductoAtributoValor(
                producto_id=product_id,
                atributo_id=optional_attribute_id,
                valor_boolean=True,
                usuario_auditoria="fixture",
                activo=True,
            )
            session.add(optional_value)
            session.commit()
            optional_value_id = optional_value.id

            ProductoService().update_integral(
                session,
                product_id,
                ProductoIntegralUpdate(
                    categoria_principal_id=category_id,
                    atributos=[
                        {"atributo_id": str(required_attribute_id), "valor": 2400},
                        {"atributo_id": str(optional_attribute_id), "valor": None},
                    ],
                ),
                actor_id=uuid4(),
            )
    finally:
        reset_current_company_id(company_token)

    with Session(engine) as session:
        required_value = session.exec(
            select(ProductoAtributoValor).where(
                ProductoAtributoValor.producto_id == product_id,
                ProductoAtributoValor.atributo_id == required_attribute_id,
                ProductoAtributoValor.activo.is_(True),
            )
        ).one()
        historical_optional = session.exec(
            select(ProductoAtributoValor)
            .where(ProductoAtributoValor.id == optional_value_id)
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        ).one()
        assert required_value.valor_integer == 2400
        assert historical_optional.activo is False
        assert historical_optional.valor_boolean is True


def test_update_integral_rejects_category_change_without_preview():
    engine = _engine()
    with Session(engine) as session:
        company_id, category_id, _attribute_id, tax_id = _seed_catalog(
            session, default_value="1600"
        )
        target_category = Categoria(
            nombre="Teclado",
            es_padre=False,
            is_default=False,
            usuario_auditoria="fixture",
            activo=True,
        )
        session.add(target_category)
        session.commit()
        target_category_id = target_category.id

    company_token = set_current_company_id(str(company_id))
    try:
        with Session(engine) as session:
            product = ProductoService().create_integral(
                session, _payload(category_id, tax_id), actor_id=uuid4()
            )
            product_id = product.id
            with pytest.raises(HTTPException) as error:
                ProductoService().update_integral(
                    session,
                    product_id,
                    ProductoIntegralUpdate(categoria_principal_id=target_category_id),
                    actor_id=uuid4(),
                )
            assert error.value.status_code == 409
            assert error.value.detail["code"] == "PRODUCT_CATEGORY_CHANGE_REQUIRES_PREVIEW"
    finally:
        reset_current_company_id(company_token)

    with Session(engine) as session:
        product = session.get(Producto, product_id)
        assert product is not None
        assert product.categoria_principal_id == category_id


def test_update_integral_rolls_back_general_fields_eav_and_audit_on_invalid_value():
    engine = _engine()
    with Session(engine) as session:
        company_id, category_id, attribute_id, tax_id = _seed_catalog(
            session, default_value="1600"
        )

    company_token = set_current_company_id(str(company_id))
    try:
        with Session(engine) as session:
            product = ProductoService().create_integral(
                session, _payload(category_id, tax_id), actor_id=uuid4()
            )
            product_id = product.id
            audit_before = set(session.exec(select(AuditLog.id)).all())
            with pytest.raises(HTTPException) as error:
                ProductoService().update_integral(
                    session,
                    product_id,
                    ProductoIntegralUpdate(
                        categoria_principal_id=category_id,
                        nombre="No debe persistir",
                        atributos=[
                            {"atributo_id": str(attribute_id), "valor": "no-entero"}
                        ],
                    ),
                    actor_id=uuid4(),
                )
            assert error.value.status_code == 422
            assert error.value.detail["code"] == "PRODUCT_ATTRIBUTE_VALUE_INVALID"
            assert not session.in_transaction()
    finally:
        reset_current_company_id(company_token)

    with Session(engine) as session:
        product = session.get(Producto, product_id)
        assert product is not None
        assert product.nombre != "No debe persistir"
        value = session.exec(
            select(ProductoAtributoValor).where(
                ProductoAtributoValor.producto_id == product_id,
                ProductoAtributoValor.atributo_id == attribute_id,
                ProductoAtributoValor.activo.is_(True),
            )
        ).one()
        assert value.valor_integer == 1600
        assert set(session.exec(select(AuditLog.id)).all()) == audit_before


def test_category_change_preview_reports_impact_and_never_mutates():
    engine = _engine()
    with Session(engine) as session:
        company_id, current_category_id, dpi_id, tax_id = _seed_catalog(
            session, default_value="1600"
        )
        current_category = session.get(Categoria, current_category_id)
        current_category.parent_id = None
        color = Atributo(
            nombre="Color",
            codigo=f"color_{uuid4().hex[:8]}",
            tipo_dato=TipoDato.STRING,
            usuario_auditoria="fixture",
            activo=True,
        )
        material = Atributo(
            nombre="Material",
            codigo=f"material_{uuid4().hex[:8]}",
            tipo_dato=TipoDato.STRING,
            usuario_auditoria="fixture",
            activo=True,
        )
        target_category = Categoria(
            nombre="Teclados",
            es_padre=False,
            is_default=False,
            usuario_auditoria="fixture",
            activo=True,
        )
        material = Atributo(
            nombre="Material",
            codigo=f"material_{uuid4().hex[:8]}",
            tipo_dato=TipoDato.STRING,
            usuario_auditoria="fixture",
            activo=True,
        )
        switch_type = Atributo(
            nombre="Mecánico",
            codigo=f"mecanico_{uuid4().hex[:8]}",
            tipo_dato=TipoDato.BOOLEAN,
            usuario_auditoria="fixture",
            activo=True,
        )
        optional_select = Atributo(
            nombre="Layout",
            codigo=f"layout_{uuid4().hex[:8]}",
            tipo_dato=TipoDato.SELECT,
            select_options=["ANSI", "ISO"],
            usuario_auditoria="fixture",
            activo=True,
        )
        session.add_all([color, target_category, material, switch_type, optional_select])
        session.flush()
        session.add_all(
            [
                CategoriaAtributo(
                    categoria_id=current_category_id,
                    atributo_id=color.id,
                    obligatorio=False,
                    usuario_auditoria="fixture",
                    activo=True,
                ),
                CategoriaAtributo(
                    categoria_id=target_category.id,
                    atributo_id=dpi_id,
                    obligatorio=True,
                    usuario_auditoria="fixture",
                    activo=True,
                ),
                CategoriaAtributo(
                    categoria_id=target_category.id,
                    atributo_id=material.id,
                    obligatorio=True,
                    valor_default="Acero",
                    usuario_auditoria="fixture",
                    activo=True,
                ),
                CategoriaAtributo(
                    categoria_id=target_category.id,
                    atributo_id=switch_type.id,
                    obligatorio=True,
                    usuario_auditoria="fixture",
                    activo=True,
                ),
                CategoriaAtributo(
                    categoria_id=target_category.id,
                    atributo_id=optional_select.id,
                    obligatorio=False,
                    usuario_auditoria="fixture",
                    activo=True,
                ),
            ]
        )
        session.commit()
        target_category_id = target_category.id
        color_id = color.id
        material_id = material.id
        switch_id = switch_type.id
        optional_select_id = optional_select.id

    company_token = set_current_company_id(str(company_id))
    try:
        with Session(engine) as session:
            product = ProductoService().create_integral(
                session,
                ProductoIntegralCreate(
                    nombre=f"Mouse {uuid4().hex[:8]}",
                    tipo=TipoProducto.BIEN,
                    pvp=Decimal("10.00"),
                    categoria_principal_id=current_category_id,
                    impuesto_catalogo_ids=[tax_id],
                    atributos=[
                        {"atributo_id": str(color_id), "valor": "Negro"},
                    ],
                ),
                actor_id=uuid4(),
            )
            product_id = product.id
            before_product = session.get(Producto, product_id).model_dump()
            before_values = [
                row.model_dump()
                for row in session.exec(
                    select(ProductoAtributoValor).where(
                        ProductoAtributoValor.producto_id == product_id
                    )
                ).all()
            ]
            before_audit_count = session.scalar(select(func.count()).select_from(AuditLog))
            preview_payload = ProductoCambioCategoriaPreviewInput(
                categoria_principal_id=target_category_id,
                atributos=[
                    {"atributo_id": str(color_id), "valor": "Negro"},
                ],
            )
            preview_actor = uuid4()
            preview = preview_product_category_change(
                session,
                product_id,
                preview_payload,
                actor_id=preview_actor,
            )

            assert preview.requiere_confirmacion is True
            assert preview.categoria_actual_id == current_category_id
            assert preview.categoria_actual_ruta == "Mouse"
            assert preview.categoria_destino_id == target_category_id
            assert preview.categoria_destino_ruta == "Teclados"
            assert preview.conteos["atributos_conservados"] == 1
            assert preview.conteos["valores_desactivados"] == 1
            assert preview.conteos["defaults_disponibles"] == 1
            assert preview.conteos["nuevos_obligatorios"] == 2
            assert preview.conteos["faltantes"] == 1
            assert preview.conservados[0].atributo_id == dpi_id
            assert preview.desactivados[0].atributo_id == color_id
            assert preview.defaults[0].atributo_id == material_id
            assert preview.defaults[0].valor == "Acero"
            assert preview.faltantes[0].atributo_id == switch_id
            assert len(preview.precondicion_preview) > 20
            state = product_category_preview_state(
                session,
                session.get(Producto, product_id),
                current_category_id,
                target_category_id,
                [current_category_id],
            )
            payload_data = product_category_preview_payload(
                preview_payload.categoria_principal_id,
                preview_payload.atributos,
            )
            signer = product_preview_signer()
            signer.verify(
                preview.precondicion_preview,
                operation=OPERATION,
                target=f"/api/v1/productos/{product_id}/previsualizar-cambio-categoria",
                actor=str(preview_actor),
                payload=payload_data,
                state=state,
            )
            with pytest.raises(HTTPException) as stale_actor:
                signer.verify(
                    preview.precondicion_preview,
                    operation=OPERATION,
                    target=f"/api/v1/productos/{product_id}/previsualizar-cambio-categoria",
                    actor=str(uuid4()),
                    payload=payload_data,
                    state=state,
                )
            assert stale_actor.value.status_code == 409

            material_mapping = session.exec(
                select(CategoriaAtributo).where(
                    CategoriaAtributo.categoria_id == target_category_id,
                    CategoriaAtributo.atributo_id == material_id,
                )
            ).one()
            material_mapping.valor_default = "Aluminio"
            session.add(material_mapping)
            session.flush()
            stale_state = product_category_preview_state(
                session,
                session.get(Producto, product_id),
                current_category_id,
                target_category_id,
                [current_category_id],
            )
            with pytest.raises(HTTPException) as stale_catalog:
                signer.verify(
                    preview.precondicion_preview,
                    operation=OPERATION,
                    target=f"/api/v1/productos/{product_id}/previsualizar-cambio-categoria",
                    actor=str(preview_actor),
                    payload=payload_data,
                    state=stale_state,
                )
            assert stale_catalog.value.status_code == 409
            assert session.get(Producto, product_id).model_dump() == before_product
            after_values = [
                row.model_dump()
                for row in session.exec(
                    select(ProductoAtributoValor).where(
                        ProductoAtributoValor.producto_id == product_id
                    )
                ).all()
            ]
            assert after_values == before_values
            assert session.scalar(select(func.count()).select_from(AuditLog)) == before_audit_count

            invalid_preview = preview_product_category_change(
                session,
                product_id,
                ProductoCambioCategoriaPreviewInput(
                    categoria_principal_id=target_category_id,
                    atributos=[
                        {"atributo_id": str(switch_id), "valor": "maybe"},
                        {"atributo_id": str(optional_select_id), "valor": "invalid"},
                    ],
                ),
                actor_id=uuid4(),
            )
            assert invalid_preview.conteos["incompatibles"] == 2
            assert invalid_preview.conteos["faltantes"] == 0
            assert invalid_preview.incompatibles[0].atributo_id == switch_id
            assert optional_select_id in {
                item.atributo_id for item in invalid_preview.incompatibles
            }

            null_required_preview = preview_product_category_change(
                session,
                product_id,
                ProductoCambioCategoriaPreviewInput(
                    categoria_principal_id=target_category_id,
                    atributos=[
                        {"atributo_id": str(material_id), "valor": None},
                    ],
                ),
                actor_id=uuid4(),
            )
            assert null_required_preview.conteos["defaults_disponibles"] == 0
            assert null_required_preview.conteos["faltantes"] == 2
            assert material_id in {
                item.atributo_id for item in null_required_preview.faltantes
            }
    finally:
        reset_current_company_id(company_token)


def test_category_change_confirmation_rejects_stale_then_commits_exact_preview():
    engine = _engine()
    with Session(engine) as session:
        company_id, current_category_id, dpi_id, tax_id = _seed_catalog(
            session, default_value="1600"
        )
        color = Atributo(
            nombre="Color",
            codigo=f"color_{uuid4().hex[:8]}",
            tipo_dato=TipoDato.STRING,
            usuario_auditoria="fixture",
            activo=True,
        )
        material = Atributo(
            nombre="Material",
            codigo=f"material_{uuid4().hex[:8]}",
            tipo_dato=TipoDato.STRING,
            usuario_auditoria="fixture",
            activo=True,
        )
        target_category = Categoria(
            nombre="Teclados",
            es_padre=False,
            is_default=False,
            usuario_auditoria="fixture",
            activo=True,
        )
        session.add_all([color, material, target_category])
        session.flush()
        session.add_all(
            [
                CategoriaAtributo(
                    categoria_id=current_category_id,
                    atributo_id=color.id,
                    obligatorio=False,
                    usuario_auditoria="fixture",
                    activo=True,
                ),
                CategoriaAtributo(
                    categoria_id=target_category.id,
                    atributo_id=dpi_id,
                    obligatorio=True,
                    usuario_auditoria="fixture",
                    activo=True,
                ),
                CategoriaAtributo(
                    categoria_id=target_category.id,
                    atributo_id=material.id,
                    obligatorio=True,
                    valor_default="Acero",
                    usuario_auditoria="fixture",
                    activo=True,
                ),
            ]
        )
        session.commit()
        target_category_id = target_category.id
        color_id = color.id
        material_id = material.id

    company_token = set_current_company_id(str(company_id))
    try:
        with Session(engine) as session:
            product = ProductoService().create_integral(
                session,
                ProductoIntegralCreate(
                    nombre=f"Mouse {uuid4().hex[:8]}",
                    tipo=TipoProducto.BIEN,
                    pvp=Decimal("10.00"),
                    categoria_principal_id=current_category_id,
                    impuesto_catalogo_ids=[tax_id],
                    atributos=[
                        {"atributo_id": str(color_id), "valor": "Negro"},
                    ],
                ),
                actor_id=uuid4(),
            )
            product_id = product.id

        actor_id = uuid4()
        preview_payload = ProductoCambioCategoriaPreviewInput(
            categoria_principal_id=target_category_id,
            atributos=[{"atributo_id": str(dpi_id), "valor": 2200}],
        )
        with Session(engine) as session:
            preview = preview_product_category_change(
                session, product_id, preview_payload, actor_id=actor_id
            )
            assert [(item.atributo_id, item.valor) for item in preview.defaults] == [
                (material_id, "Acero")
            ]
        valid_payload = ProductoIntegralUpdate(
            categoria_principal_id=target_category_id,
            atributos=[{"atributo_id": str(dpi_id), "valor": 2200}],
            precondicion_preview=preview.precondicion_preview,
        )

        with Session(engine) as session:
            with pytest.raises(HTTPException) as stale:
                ProductoService().update_integral(
                    session,
                    product_id,
                    ProductoIntegralUpdate(
                        categoria_principal_id=target_category_id,
                        atributos=[{"atributo_id": str(dpi_id), "valor": 2300}],
                        precondicion_preview=preview.precondicion_preview,
                    ),
                    actor_id=actor_id,
                )
            assert stale.value.status_code == 409
            assert stale.value.detail["code"] == "CATALOG_PREVIEW_STALE"

        with Session(engine) as session:
            product_before = session.get(Producto, product_id)
            assert product_before is not None
            assert product_before.categoria_principal_id == current_category_id
            assert session.exec(
                select(ProductoCategoria).where(
                    ProductoCategoria.producto_id == product_id,
                    ProductoCategoria.categoria_id == current_category_id,
                )
            ).first() is not None

            updated = ProductoService().update_integral(
                session,
                product_id,
                valid_payload,
                actor_id=actor_id,
            )
            assert updated is not None
            assert updated.categoria_principal_id == target_category_id

        with Session(engine) as session:
            active_categories = session.exec(
                select(ProductoCategoria.categoria_id).where(
                    ProductoCategoria.producto_id == product_id
                )
            ).all()
            assert active_categories == [target_category_id]
            values = session.exec(
                select(ProductoAtributoValor)
                .where(ProductoAtributoValor.producto_id == product_id)
                .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
            ).all()
            by_attribute = {value.atributo_id: value for value in values}
            assert by_attribute[dpi_id].activo is True
            assert by_attribute[dpi_id].valor_integer == 2200
            assert by_attribute[color_id].activo is False
            assert by_attribute[color_id].valor_string == "Negro"
            assert by_attribute[material_id].activo is True
            assert by_attribute[material_id].valor_string == "Acero"
    finally:
        reset_current_company_id(company_token)


@pytest.mark.parametrize("failure_point", ["bridge", "tax", "eav", "audit"])
def test_create_integral_rolls_back_every_table_when_persistence_step_fails(
    failure_point: str,
):
    engine = _engine()
    with Session(engine) as session:
        company_id, category_id, attribute_id, tax_id = _seed_catalog(
            session, default_value="1600"
        )

    if failure_point in {"bridge", "tax"}:
        table_name = (
            "tbl_producto_categoria"
            if failure_point == "bridge"
            else "tbl_producto_impuesto"
        )
        with engine.begin() as connection:
            connection.exec_driver_sql(
                f"CREATE TRIGGER reject_integral_{failure_point} "
                f"BEFORE INSERT ON {table_name} "
                "BEGIN SELECT RAISE(ABORT, 'forced persistence failure'); END"
            )

    values = (
        [{"atributo_id": str(attribute_id), "valor": "not-an-integer"}]
        if failure_point == "eav"
        else []
    )
    payload = ProductoIntegralCreate.model_validate(
        {
            **_payload(category_id, tax_id).model_dump(),
            "atributos": values,
        }
    )
    company_token = set_current_company_id(str(company_id))
    try:
        with Session(engine) as session:
            def fail_tax_audit(audit_session, **kwargs):
                if kwargs.get("action") == "CREATE_PRODUCT_TAX_PROFILE":
                    raise RuntimeError("forced audit failure")
                return record_domain_change(audit_session, **kwargs)

            try:
                if failure_point == "audit":
                    with patch(
                        "osiris.modules.inventario.producto.service.record_domain_change",
                        side_effect=fail_tax_audit,
                    ):
                        with pytest.raises(Exception):
                            ProductoService().create_integral(
                                session, payload, actor_id=uuid4()
                            )
                else:
                    with pytest.raises(Exception):
                        ProductoService().create_integral(
                            session, payload, actor_id=uuid4()
                        )
                assert not session.in_transaction()
            except Exception:
                raise
    finally:
        reset_current_company_id(company_token)

    with Session(engine) as session:
        assert session.exec(select(Producto)).all() == []
        assert session.exec(select(ProductoCategoria)).all() == []
        assert session.exec(select(ProductoImpuesto)).all() == []
        assert session.exec(select(ProductoAtributoValor)).all() == []
        assert session.exec(
            select(AuditLog).where(AuditLog.accion.in_(
                [
                    "CREATE_PRODUCT_INTEGRAL",
                    "SET_PRODUCT_PRIMARY_CATEGORY",
                    "CREATE_PRODUCT_TAX_PROFILE",
                    "UPSERT_PRODUCT_ATTRIBUTE_VALUE",
                ]
            ))
        ).all() == []


def test_category_change_preview_endpoint_returns_json_without_writes():
    engine = _engine()
    with Session(engine) as session:
        company_id, current_category_id, _attribute_id, tax_id = _seed_catalog(
            session, default_value="1600"
        )
        target_category = Categoria(
            nombre="Teclados",
            es_padre=False,
            is_default=False,
            usuario_auditoria="fixture",
            activo=True,
        )
        session.add(target_category)
        session.commit()
        target_category_id = target_category.id

    company_token = set_current_company_id(str(company_id))
    try:
        with Session(engine) as session:
            product = ProductoService().create_integral(
                session, _payload(current_category_id, tax_id), actor_id=uuid4()
            )
            product_id = product.id
        actor_id = uuid4()
        app = FastAPI()
        app.include_router(producto_router)

        def override_session():
            with Session(engine) as session:
                yield session

        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[update_product_permission] = lambda: type(
            "TestActor", (), {"id": actor_id}
        )()
        with Session(engine) as session:
            audit_before = session.scalar(select(func.count()).select_from(AuditLog))

        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/productos/{product_id}/previsualizar-cambio-categoria",
                json={"categoria_principal_id": str(target_category_id)},
            )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["operacion"] == "CHANGE_PRODUCT_PRIMARY_CATEGORY"
        assert body["producto_id"] == str(product_id)
        assert body["categoria_actual_ruta"] == "Mouse"
        assert body["categoria_destino_ruta"] == "Teclados"
        assert body["requiere_confirmacion"] is True
        assert len(body["precondicion_preview"]) > 20
        with Session(engine) as session:
            assert session.scalar(select(func.count()).select_from(AuditLog)) == audit_before
            product = session.get(Producto, product_id)
            assert product is not None
            assert product.categoria_principal_id == current_category_id
    finally:
        reset_current_company_id(company_token)


def test_category_change_confirmation_rejects_preview_stale_after_mapping_changes_in_second_session():
    engine = _engine()
    with Session(engine) as session:
        company_id, current_category_id, dpi_id, tax_id = _seed_catalog(
            session, default_value="1600"
        )
        target_category = Categoria(
            nombre="Teclados",
            es_padre=False,
            is_default=False,
            usuario_auditoria="fixture",
            activo=True,
        )
        session.add(target_category)
        session.flush()
        target_mapping = CategoriaAtributo(
            categoria_id=target_category.id,
            atributo_id=dpi_id,
            obligatorio=True,
            valor_default="2400",
            usuario_auditoria="fixture",
            activo=True,
        )
        session.add(target_mapping)
        session.commit()
        target_category_id = target_category.id
        target_mapping_id = target_mapping.id

    company_token = set_current_company_id(str(company_id))
    try:
        with Session(engine) as session:
            product = ProductoService().create_integral(
                session, _payload(current_category_id, tax_id), actor_id=uuid4()
            )
            product_id = product.id

        actor_id = uuid4()
        preview_input = ProductoCambioCategoriaPreviewInput(
            categoria_principal_id=target_category_id,
            atributos=[{"atributo_id": str(dpi_id), "valor": 2400}],
        )
        with Session(engine) as preview_session:
            preview = preview_product_category_change(
                preview_session, product_id, preview_input, actor_id=actor_id
            )

        with Session(engine) as catalog_session:
            mapping = catalog_session.get(CategoriaAtributo, target_mapping_id)
            assert mapping is not None
            mapping.valor_default = "3200"
            catalog_session.add(mapping)
            catalog_session.commit()

        with Session(engine) as update_session:
            with pytest.raises(HTTPException) as stale:
                ProductoService().update_integral(
                    update_session,
                    product_id,
                    ProductoIntegralUpdate(
                        categoria_principal_id=target_category_id,
                        atributos=[{"atributo_id": str(dpi_id), "valor": 2400}],
                        precondicion_preview=preview.precondicion_preview,
                    ),
                    actor_id=actor_id,
                )
            assert stale.value.status_code == 409
            assert stale.value.detail["code"] == "CATALOG_PREVIEW_STALE"

        with Session(engine) as verify_session:
            product = verify_session.get(Producto, product_id)
            assert product is not None
            assert product.categoria_principal_id == current_category_id
            eav = verify_session.exec(
                select(ProductoAtributoValor).where(
                    ProductoAtributoValor.producto_id == product_id,
                    ProductoAtributoValor.atributo_id == dpi_id,
                    ProductoAtributoValor.activo.is_(True),
                )
            ).one()
            assert eav.valor_integer == 1600
    finally:
        reset_current_company_id(company_token)


def test_postgresql_concurrent_category_mapping_change_rejects_confirmation_atomically(
    postgresql_product_engine: Engine,
) -> None:
    engine = postgresql_product_engine
    with Session(engine) as session:
        company_id, current_category_id, dpi_id, tax_id = _seed_catalog(
            session, default_value="1600"
        )
        target_category = Categoria(
            nombre="Concurrent keyboards",
            es_padre=False,
            is_default=False,
            usuario_auditoria="fixture",
            activo=True,
        )
        session.add(target_category)
        session.flush()
        target_mapping = CategoriaAtributo(
            categoria_id=target_category.id,
            atributo_id=dpi_id,
            obligatorio=True,
            valor_default="2400",
            usuario_auditoria="fixture",
            activo=True,
        )
        session.add(target_mapping)
        session.commit()
        target_category_id = target_category.id
        target_mapping_id = target_mapping.id

    company_token = set_current_company_id(str(company_id))
    try:
        with Session(engine) as session:
            product = ProductoService().create_integral(
                session, _payload(current_category_id, tax_id), actor_id=uuid4()
            )
            product_id = product.id

        actor_id = uuid4()
        preview_input = ProductoCambioCategoriaPreviewInput(
            categoria_principal_id=target_category_id,
            atributos=[{"atributo_id": str(dpi_id), "valor": 2400}],
        )
        with Session(engine) as session:
            preview = preview_product_category_change(
                session, product_id, preview_input, actor_id=actor_id
            )

        with Session(engine) as session:
            lock_available = session.exec(
                sa.text("SELECT pg_try_advisory_xact_lock(:key)"),
                params={"key": CATALOG_MUTATION_LOCK_KEY},
            ).scalar_one()
            assert lock_available is True

        mapping_written = Event()
        release_mapping_transaction = Event()
        confirmation_pid_ready = Event()
        confirmation_pid: list[int] = []
        mapping_errors: list[BaseException] = []
        confirmation_errors: list[BaseException] = []

        def mutate_mapping_under_lock() -> None:
            try:
                with Session(engine) as session:
                    CategoriaService.acquire_hierarchy_mutation_lock(session)
                    mapping = session.get(CategoriaAtributo, target_mapping_id)
                    assert mapping is not None
                    mapping.valor_default = "3200"
                    session.add(mapping)
                    mapping_written.set()
                    assert release_mapping_transaction.wait(timeout=10)
                    session.commit()
            except BaseException as error:
                mapping_errors.append(error)
                mapping_written.set()
                raise

        def confirm_stale_preview() -> HTTPException | None:
            assert mapping_written.wait(timeout=10)
            assert not mapping_errors, repr(mapping_errors)
            token = set_current_company_id(str(company_id))
            try:
                with Session(engine) as session:
                    confirmation_pid.append(
                        int(session.exec(sa.text("SELECT pg_backend_pid()")).scalar_one())
                    )
                    confirmation_pid_ready.set()
                    try:
                        ProductoService().update_integral(
                            session,
                            product_id,
                            ProductoIntegralUpdate(
                                categoria_principal_id=target_category_id,
                                atributos=[{"atributo_id": str(dpi_id), "valor": 2400}],
                                precondicion_preview=preview.precondicion_preview,
                            ),
                            actor_id=actor_id,
                        )
                    except HTTPException as error:
                        return error
            except BaseException as error:
                confirmation_errors.append(error)
                confirmation_pid_ready.set()
                raise
            finally:
                reset_current_company_id(token)
            return None

        with ThreadPoolExecutor(max_workers=2) as executor:
            mapping_future = executor.submit(mutate_mapping_under_lock)
            confirmation_future = executor.submit(confirm_stale_preview)
            try:
                assert mapping_written.wait(timeout=5)
                assert not mapping_errors, repr(mapping_errors)
                assert confirmation_pid_ready.wait(timeout=10)
                assert not confirmation_errors, repr(confirmation_errors)
                deadline = monotonic() + 5
                waiting_on_advisory_lock = False
                while monotonic() < deadline:
                    with engine.connect() as connection:
                        waiting_on_advisory_lock = bool(
                            connection.scalar(
                                sa.text(
                                    "SELECT EXISTS ("
                                    "SELECT 1 FROM pg_locks "
                                    "WHERE pid = :pid AND locktype = 'advisory' "
                                    "AND granted IS FALSE)"
                                ),
                                {"pid": confirmation_pid[0]},
                            )
                        )
                    if waiting_on_advisory_lock:
                        break
                    Event().wait(0.01)
                assert waiting_on_advisory_lock is True
                assert confirmation_future.done() is False
            finally:
                release_mapping_transaction.set()

            mapping_future.result(timeout=10)
            stale = confirmation_future.result(timeout=10)

        assert stale is not None
        assert stale.status_code == 409
        assert stale.detail["code"] == "CATALOG_PREVIEW_STALE"

        with Session(engine) as session:
            committed_mapping = session.get(CategoriaAtributo, target_mapping_id)
            assert committed_mapping is not None
            assert committed_mapping.valor_default == "3200"
            product = session.get(Producto, product_id)
            assert product is not None
            assert product.categoria_principal_id == current_category_id
            bridge_ids = session.exec(
                select(ProductoCategoria.categoria_id).where(
                    ProductoCategoria.producto_id == product_id
                )
            ).all()
            assert bridge_ids == [current_category_id]
            eav = session.exec(
                select(ProductoAtributoValor).where(
                    ProductoAtributoValor.producto_id == product_id,
                    ProductoAtributoValor.atributo_id == dpi_id,
                    ProductoAtributoValor.activo.is_(True),
                )
            ).one()
            assert eav.valor_integer == 1600
    finally:
        reset_current_company_id(company_token)
