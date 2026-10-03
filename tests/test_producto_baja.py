from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.inventario.atributo.entity import Atributo, TipoDato
from osiris.modules.inventario.bodega.entity import Bodega
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.movimientos.models import InventarioStock
from osiris.modules.inventario.producto.entity import (
    Producto,
    ProductoBodega,
    ProductoCategoria,
    ProductoImpuesto,
    TipoProducto,
)
from osiris.modules.inventario.producto.models_atributos import ProductoAtributoValor as ProductoAtributoValorRow
from osiris.modules.inventario.producto.service import ProductoService
from osiris.modules.sri.impuesto_catalogo.entity import AplicaA, ImpuestoCatalogo, TipoImpuesto
from osiris.modules.sri.tipo_contribuyente.entity import TipoContribuyente


def _engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(
        engine,
        tables=[
            AuditLog.__table__,
            TipoContribuyente.__table__,
            Empresa.__table__,
            Sucursal.__table__,
            Bodega.__table__,
            CasaComercial.__table__,
            Categoria.__table__,
            Atributo.__table__,
            Producto.__table__,
            ProductoCategoria.__table__,
            ProductoBodega.__table__,
            ProductoImpuesto.__table__,
            ProductoAtributoValorRow.__table__,
            ImpuestoCatalogo.__table__,
            InventarioStock.__table__,
        ],
    )
    return engine


def _seed_product(session: Session, *, stock: Decimal = Decimal("0.0000")):
    session.add(TipoContribuyente(codigo="01", nombre="Sociedad", activo=True))
    company = Empresa(
        razon_social="Empresa Test",
        ruc="1790012345001",
        direccion_matriz="Direccion",
        tipo_contribuyente_id="01",
        usuario_auditoria="test",
        activo=True,
    )
    session.add(company)
    session.flush()
    branch = Sucursal(
        codigo="001",
        nombre="Matriz",
        direccion="Direccion",
        es_matriz=True,
        empresa_id=company.id,
        usuario_auditoria="test",
        activo=True,
    )
    session.add(branch)
    session.flush()
    warehouse = Bodega(
        codigo_bodega="B1",
        nombre_bodega="Bodega",
        empresa_id=company.id,
        sucursal_id=branch.id,
        usuario_auditoria="test",
        activo=True,
    )
    tax = ImpuestoCatalogo(
        tipo_impuesto=TipoImpuesto.IVA,
        codigo_tipo_impuesto="2",
        codigo_sri="0",
        descripcion="IVA 0%",
        vigente_desde=date(2020, 1, 1),
        aplica_a=AplicaA.AMBOS,
        porcentaje_iva=Decimal("0"),
        usuario_auditoria="test",
        activo=True,
    )
    attribute = Atributo(nombre=f"Color-{uuid4().hex[:6]}", tipo_dato=TipoDato.STRING, usuario_auditoria="test", activo=True)
    product = Producto(nombre=f"Product-{uuid4().hex[:6]}", tipo=TipoProducto.BIEN, pvp=Decimal("10.00"), cantidad=stock, usuario_auditoria="test", activo=True)
    session.add_all([warehouse, tax, attribute, product])
    session.flush()
    warehouse_relation = ProductoBodega(producto_id=product.id, bodega_id=warehouse.id, cantidad=stock, usuario_auditoria="test", activo=True)
    tax_relation = ProductoImpuesto(producto_id=product.id, empresa_id=company.id, impuesto_catalogo_id=tax.id, codigo_impuesto_sri="2", codigo_porcentaje_sri="0", tarifa=Decimal("0"), usuario_auditoria="test", activo=True)
    attribute_value = ProductoAtributoValorRow(producto_id=product.id, atributo_id=attribute.id, valor_string="Rojo", usuario_auditoria="test", activo=True)
    session.add_all([warehouse_relation, tax_relation, attribute_value])
    if stock > 0:
        session.add(
            InventarioStock(
                bodega_id=warehouse.id,
                producto_id=product.id,
                cantidad_actual=stock,
                costo_promedio_vigente=Decimal("0"),
                usuario_auditoria="test",
                activo=True,
            )
        )
    session.commit()
    return product, warehouse_relation, tax_relation, attribute_value


def test_product_delete_soft_deactivates_operational_relations_without_stock():
    engine = _engine()
    with Session(engine) as session:
        product, warehouse_relation, tax_relation, attribute_value = _seed_product(session)

        assert ProductoService().delete(session, product.id) is True

        include_inactive = {"include_inactive": True, "populate_existing": True}
        product = session.exec(
            select(Producto)
            .where(Producto.id == product.id)
            .execution_options(**include_inactive)
        ).one()
        warehouse_relation = session.exec(
            select(ProductoBodega)
            .where(ProductoBodega.id == warehouse_relation.id)
            .execution_options(**include_inactive)
        ).one()
        tax_relation = session.exec(
            select(ProductoImpuesto)
            .where(ProductoImpuesto.id == tax_relation.id)
            .execution_options(**include_inactive)
        ).one()
        attribute_value = session.exec(
            select(ProductoAtributoValorRow)
            .where(ProductoAtributoValorRow.id == attribute_value.id)
            .execution_options(**include_inactive)
        ).one()
        audit = session.exec(
            select(AuditLog).where(
                AuditLog.entidad == "tbl_producto",
                AuditLog.entidad_id == product.id,
                AuditLog.accion == "DELETE_PRODUCT",
            )
        ).first()
        assert product.activo is False
        assert warehouse_relation.activo is False
        assert tax_relation.activo is False
        assert attribute_value.activo is False
        assert audit is not None


def test_product_delete_blocks_positive_stock_without_partial_changes():
    engine = _engine()
    with Session(engine) as session:
        product, warehouse_relation, tax_relation, attribute_value = _seed_product(session, stock=Decimal("2"))

        with pytest.raises(HTTPException) as exc_info:
            ProductoService().delete(session, product.id)

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["code"] == "PRODUCT_HAS_STOCK"
        include_inactive = {"include_inactive": True, "populate_existing": True}
        product = session.exec(
            select(Producto)
            .where(Producto.id == product.id)
            .execution_options(**include_inactive)
        ).one()
        warehouse_relation = session.exec(
            select(ProductoBodega)
            .where(ProductoBodega.id == warehouse_relation.id)
            .execution_options(**include_inactive)
        ).one()
        tax_relation = session.exec(
            select(ProductoImpuesto)
            .where(ProductoImpuesto.id == tax_relation.id)
            .execution_options(**include_inactive)
        ).one()
        attribute_value = session.exec(
            select(ProductoAtributoValorRow)
            .where(ProductoAtributoValorRow.id == attribute_value.id)
            .execution_options(**include_inactive)
        ).one()
        assert product.activo is True
        assert warehouse_relation.activo is True
        assert tax_relation.activo is True
        assert attribute_value.activo is True
