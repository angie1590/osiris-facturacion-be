from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from osiris.core.audit_context import reset_current_company_id, set_current_company_id
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.catalogo.entity import Catalogo
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.tipo_cliente.entity import TipoCliente
from osiris.modules.common.unidad.entity import Unidad
from osiris.modules.inventario.atributo.entity import Atributo, TipoDato
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.inventario.producto.entity import (
    Producto,
    ProductoCategoria,
    ProductoImpuesto,
    TipoProducto,
)
from osiris.modules.inventario.producto.models import ProductoIntegralCreate
from osiris.modules.inventario.producto.models_atributos import ProductoAtributoValor
from osiris.modules.inventario.producto.service import ProductoService
from osiris.modules.sri.impuesto_catalogo.entity import (
    AplicaA,
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
            TipoCliente.__table__,
            TipoContribuyente.__table__,
            Unidad.__table__,
            CasaComercial.__table__,
            Categoria.__table__,
            CategoriaAtributo.__table__,
            Atributo.__table__,
            Producto.__table__,
            ProductoCategoria.__table__,
            ProductoAtributoValor.__table__,
            ImpuestoCatalogo.__table__,
            ProductoImpuesto.__table__,
        ],
    )
    return engine


def _seed_catalog(session: Session, *, default_value: str | None):
    session.add(TipoContribuyente(codigo="01", nombre="Sociedad", activo=True))
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
