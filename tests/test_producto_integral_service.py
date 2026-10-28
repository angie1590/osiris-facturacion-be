from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from osiris.core.audit import record_domain_change
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from osiris.core.audit_context import reset_current_company_id, set_current_company_id
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
from osiris.modules.inventario.producto.models import ProductoIntegralUpdate
from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
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
