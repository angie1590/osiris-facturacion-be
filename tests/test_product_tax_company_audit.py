from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from fastapi import HTTPException
from osiris.core.audit_context import reset_current_company_id, set_current_company_id
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.inventario.bodega.entity import Bodega
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria.models import RecategorizarProducto
from osiris.modules.inventario.categoria.service import CategoriaService
from osiris.modules.compras.services.compra_service import CompraService
from osiris.modules.inventario.producto.entity import (
    Producto,
    ProductoBodega,
    ProductoCategoria,
    ProductoImpuesto,
    TipoProducto,
)
from osiris.modules.inventario.producto.service import ProductoService
from osiris.modules.sri.impuesto_catalogo.entity import AplicaA, ImpuestoCatalogo, TipoImpuesto
from osiris.modules.sri.tipo_contribuyente.entity import TipoContribuyente
from osiris.modules.ventas.services.venta_service import VentaService
from scripts.audit_product_tax_company_scope import build_report


def _engine():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(
        engine,
        tables=[
            TipoContribuyente.__table__,
            AuditLog.__table__,
            Empresa.__table__,
            Sucursal.__table__,
            CasaComercial.__table__,
            Producto.__table__,
            Categoria.__table__,
            ProductoCategoria.__table__,
            Bodega.__table__,
            ProductoBodega.__table__,
            ImpuestoCatalogo.__table__,
            ProductoImpuesto.__table__,
        ],
    )
    return engine


def test_audit_classifies_safe_or_ambiguous_legacy_product_tax_profiles():
    engine = _engine()
    with Session(engine) as session:
        session.add(TipoContribuyente(codigo="01", nombre="Sociedad", activo=True))
        company_a = Empresa(
            razon_social="Empresa A",
            ruc="1790012345001",
            direccion_matriz="Direccion A",
            regimen="GENERAL",
            modo_emision="ELECTRONICO",
            tipo_contribuyente_id="01",
            usuario_auditoria="test",
            activo=True,
        )
        company_b = Empresa(
            razon_social="Empresa B",
            ruc="1790012345002",
            direccion_matriz="Direccion B",
            regimen="GENERAL",
            modo_emision="ELECTRONICO",
            tipo_contribuyente_id="01",
            usuario_auditoria="test",
            activo=True,
        )
        session.add(company_a)
        session.add(company_b)
        session.flush()

        tax_allowed = ImpuestoCatalogo(
            tipo_impuesto=TipoImpuesto.IVA,
            codigo_tipo_impuesto="2",
            codigo_sri="0",
            descripcion="IVA 0%",
            vigente_desde=date(2023, 2, 1),
            aplica_a=AplicaA.AMBOS,
            porcentaje_iva=Decimal("0.00"),
            usuario_auditoria="test",
            activo=True,
        )
        tax_not_allowed = ImpuestoCatalogo(
            tipo_impuesto=TipoImpuesto.IVA,
            codigo_tipo_impuesto="2",
            codigo_sri="4",
            descripcion="IVA 15%",
            vigente_desde=date(2024, 4, 1),
            aplica_a=AplicaA.AMBOS,
            porcentaje_iva=Decimal("15.00"),
            usuario_auditoria="test",
            activo=True,
        )
        session.add(tax_allowed)
        session.add(tax_not_allowed)
        session.flush()
        company_a.impuesto_catalogo_ids = [str(tax_allowed.id)]
        company_b.impuesto_catalogo_ids = [str(tax_allowed.id)]

        bodegas = [
            Bodega(codigo_bodega=f"BOD-{index}", nombre_bodega=f"Bodega {index}", empresa_id=company_id, usuario_auditoria="test", activo=True)
            for index, company_id in enumerate((company_a.id, company_a.id, company_b.id), start=1)
        ]
        session.add_all(bodegas)
        session.flush()

        safe = Producto(nombre="Seguro", tipo=TipoProducto.BIEN, usuario_auditoria="test", activo=True)
        no_scope = Producto(nombre="Sin bodega", tipo=TipoProducto.BIEN, usuario_auditoria="test", activo=True)
        multi_scope = Producto(nombre="Multiempresa", tipo=TipoProducto.BIEN, usuario_auditoria="test", activo=True)
        disallowed = Producto(nombre="No permitido", tipo=TipoProducto.BIEN, usuario_auditoria="test", activo=True)
        session.add_all([safe, no_scope, multi_scope, disallowed])
        session.flush()

        session.add_all(
            [
                ProductoBodega(producto_id=safe.id, bodega_id=bodegas[0].id, cantidad=Decimal("0"), usuario_auditoria="test", activo=True),
                ProductoBodega(producto_id=multi_scope.id, bodega_id=bodegas[1].id, cantidad=Decimal("0"), usuario_auditoria="test", activo=True),
                ProductoBodega(producto_id=multi_scope.id, bodega_id=bodegas[2].id, cantidad=Decimal("0"), usuario_auditoria="test", activo=True),
                ProductoBodega(producto_id=disallowed.id, bodega_id=bodegas[0].id, cantidad=Decimal("0"), usuario_auditoria="test", activo=True),
                ProductoImpuesto(producto_id=safe.id, impuesto_catalogo_id=tax_allowed.id, codigo_impuesto_sri="2", codigo_porcentaje_sri="0", tarifa=Decimal("0"), usuario_auditoria="test", activo=True),
                ProductoImpuesto(producto_id=no_scope.id, impuesto_catalogo_id=tax_allowed.id, codigo_impuesto_sri="2", codigo_porcentaje_sri="0", tarifa=Decimal("0"), usuario_auditoria="test", activo=True),
                ProductoImpuesto(producto_id=multi_scope.id, impuesto_catalogo_id=tax_allowed.id, codigo_impuesto_sri="2", codigo_porcentaje_sri="0", tarifa=Decimal("0"), usuario_auditoria="test", activo=True),
                ProductoImpuesto(producto_id=disallowed.id, impuesto_catalogo_id=tax_not_allowed.id, codigo_impuesto_sri="2", codigo_porcentaje_sri="4", tarifa=Decimal("15"), usuario_auditoria="test", activo=True),
            ]
        )
        session.commit()

        report = build_report(session, today=date(2026, 10, 2))
        status_by_product = {row["producto_nombre"]: row["status"] for row in report["relaciones"]}

        assert status_by_product == {
            "Seguro": "SAFE_SINGLE_COMPANY",
            "Sin bodega": "NO_ACTIVE_WAREHOUSE_SCOPE",
            "Multiempresa": "MULTIPLE_COMPANY_SCOPE",
            "No permitido": "TAX_NOT_CONFIGURED_FOR_COMPANY",
        }
        assert report["total_relaciones"] == 4
        assert len(report["requieren_revision"]) == 3


def test_pending_recategorization_count_is_scoped_to_authenticated_company():
    engine = _engine()
    with Session(engine) as session:
        session.add(TipoContribuyente(codigo="01", nombre="Sociedad", activo=True))
        company_a = Empresa(
            razon_social="Empresa A",
            ruc="1790012345001",
            direccion_matriz="Direccion A",
            regimen="GENERAL",
            modo_emision="ELECTRONICO",
            tipo_contribuyente_id="01",
            usuario_auditoria="test",
            activo=True,
        )
        company_b = Empresa(
            razon_social="Empresa B",
            ruc="1790012345002",
            direccion_matriz="Direccion B",
            regimen="GENERAL",
            modo_emision="ELECTRONICO",
            tipo_contribuyente_id="01",
            usuario_auditoria="test",
            activo=True,
        )
        session.add_all([company_a, company_b])
        session.flush()
        warehouse_a = Bodega(
            codigo_bodega="BA",
            nombre_bodega="Bodega A",
            empresa_id=company_a.id,
            usuario_auditoria="test",
            activo=True,
        )
        warehouse_b = Bodega(
            codigo_bodega="BB",
            nombre_bodega="Bodega B",
            empresa_id=company_b.id,
            usuario_auditoria="test",
            activo=True,
        )
        bucket = Categoria(
            nombre="Sin clasificar",
            es_padre=False,
            is_default=True,
            usuario_auditoria="test",
            activo=True,
        )
        regular = Categoria(
            nombre="Regular",
            es_padre=False,
            usuario_auditoria="test",
            activo=True,
        )
        pending_product = Producto(nombre="Pendiente A", tipo=TipoProducto.BIEN, usuario_auditoria="test", activo=True)
        regular_product = Producto(nombre="Regular B", tipo=TipoProducto.BIEN, usuario_auditoria="test", activo=True)
        session.add_all([warehouse_a, warehouse_b, bucket, regular, pending_product, regular_product])
        session.flush()
        session.add_all(
            [
                ProductoCategoria(producto_id=pending_product.id, categoria_id=bucket.id),
                ProductoCategoria(producto_id=regular_product.id, categoria_id=regular.id),
                ProductoBodega(producto_id=pending_product.id, bodega_id=warehouse_a.id, cantidad=Decimal("0"), usuario_auditoria="test", activo=True),
                ProductoBodega(producto_id=regular_product.id, bodega_id=warehouse_b.id, cantidad=Decimal("0"), usuario_auditoria="test", activo=True),
            ]
        )
        session.commit()

        token = set_current_company_id(str(company_a.id))
        try:
            assert CategoriaService().contar_productos_sin_recategorizar(session) == 1
        finally:
            reset_current_company_id(token)

        token = set_current_company_id(str(company_b.id))
        try:
            assert CategoriaService().contar_productos_sin_recategorizar(session) == 0
        finally:
            reset_current_company_id(token)

        with pytest.raises(HTTPException, match="empresa autenticada"):
            CategoriaService().contar_productos_sin_recategorizar(session)


def test_recategorize_moves_company_product_and_deactivates_empty_bucket():
    engine = _engine()
    with Session(engine) as session:
        session.add(TipoContribuyente(codigo="01", nombre="Sociedad", activo=True))
        company = Empresa(
            razon_social="Empresa A",
            ruc="1790012345001",
            direccion_matriz="Direccion A",
            regimen="GENERAL",
            modo_emision="ELECTRONICO",
            tipo_contribuyente_id="01",
            usuario_auditoria="test",
            activo=True,
        )
        session.add(company)
        session.flush()
        warehouse = Bodega(
            codigo_bodega="BA",
            nombre_bodega="Bodega A",
            empresa_id=company.id,
            usuario_auditoria="test",
            activo=True,
        )
        parent = Categoria(nombre="Computadoras", es_padre=True, usuario_auditoria="test", activo=True)
        session.add_all([warehouse, parent])
        session.flush()
        bucket = Categoria(
            nombre="Sin clasificar",
            es_padre=False,
            is_default=True,
            parent_id=parent.id,
            usuario_auditoria="test",
            activo=True,
        )
        target = Categoria(
            nombre="Laptops",
            es_padre=False,
            parent_id=parent.id,
            usuario_auditoria="test",
            activo=True,
        )
        product = Producto(nombre="Equipo A", tipo=TipoProducto.BIEN, usuario_auditoria="test", activo=True)
        session.add_all([bucket, target, product])
        session.flush()
        session.add_all(
            [
                ProductoCategoria(producto_id=product.id, categoria_id=bucket.id),
                ProductoBodega(producto_id=product.id, bodega_id=warehouse.id, cantidad=Decimal("0"), usuario_auditoria="test", activo=True),
            ]
        )
        session.commit()

        token = set_current_company_id(str(company.id))
        try:
            service = CategoriaService()
            pending = service.listar_productos_sin_recategorizar(session)
            assert [item["producto_id"] for item in pending] == [product.id]
            result = service.recategorizar_productos(
                session,
                [RecategorizarProducto(producto_id=product.id, categoria_id=target.id)],
            )
            assert result == {"recategorized": 1}
            assert service.contar_productos_sin_recategorizar(session) == 0
        finally:
            reset_current_company_id(token)

        session.refresh(bucket)
        category_ids = session.exec(
            select(ProductoCategoria.categoria_id).where(ProductoCategoria.producto_id == product.id)
        ).all()
        assert bucket.activo is False
        assert category_ids == [target.id]


def test_purchase_and_sale_snapshots_read_only_the_selected_company_profile():
    engine = _engine()
    with Session(engine) as session:
        session.add(TipoContribuyente(codigo="01", nombre="Sociedad", activo=True))
        companies = [
            Empresa(
                razon_social=f"Empresa {suffix}",
                ruc=f"179001234500{suffix}",
                direccion_matriz="Direccion",
                regimen="GENERAL",
                modo_emision="ELECTRONICO",
                tipo_contribuyente_id="01",
                usuario_auditoria="test",
                activo=True,
            )
            for suffix in (1, 2)
        ]
        product = Producto(nombre="Shared product", tipo=TipoProducto.BIEN, usuario_auditoria="test", activo=True)
        session.add_all([*companies, product])
        session.flush()
        taxes = [
            ImpuestoCatalogo(
                tipo_impuesto=TipoImpuesto.IVA,
                codigo_tipo_impuesto="2",
                codigo_sri=code,
                descripcion=f"IVA {code}",
                vigente_desde=date(2020, 1, 1),
                aplica_a=AplicaA.AMBOS,
                porcentaje_iva=Decimal(rate),
                usuario_auditoria="test",
                activo=True,
            )
            for code, rate in (("0", "0"), ("4", "15"))
        ]
        session.add_all(taxes)
        session.flush()
        profiles = [
            ProductoImpuesto(
                producto_id=product.id,
                empresa_id=company.id,
                impuesto_catalogo_id=tax.id,
                codigo_impuesto_sri="2",
                codigo_porcentaje_sri=tax.codigo_sri,
                tarifa=tax.porcentaje_iva or Decimal("0"),
                usuario_auditoria="test",
                activo=True,
            )
            for company, tax in zip(companies, taxes, strict=True)
        ]
        session.add_all(profiles)
        session.commit()

        purchase_a = CompraService._snapshot_impuestos_producto(session, product.id, companies[0].id)
        sale_a = VentaService._snapshot_impuestos_producto(session, product.id, companies[0].id)
        purchase_b = CompraService._snapshot_impuestos_producto(session, product.id, companies[1].id)
        sale_b = VentaService._snapshot_impuestos_producto(session, product.id, companies[1].id)

        assert [(tax.codigo_porcentaje_sri, tax.tarifa) for tax in purchase_a] == [("0", Decimal("0.0000"))]
        assert [(tax.codigo_porcentaje_sri, tax.tarifa) for tax in sale_a] == [("0", Decimal("0.0000"))]
        assert [(tax.codigo_porcentaje_sri, tax.tarifa) for tax in purchase_b] == [("4", Decimal("15.0000"))]
        assert [(tax.codigo_porcentaje_sri, tax.tarifa) for tax in sale_b] == [("4", Decimal("15.0000"))]


def test_invalid_profile_update_rolls_back_product_and_existing_company_assignment():
    engine = _engine()
    with Session(engine) as session:
        session.add(TipoContribuyente(codigo="01", nombre="Sociedad", activo=True))
        company = Empresa(
            razon_social="Empresa A",
            ruc="1790012345001",
            direccion_matriz="Direccion A",
            regimen="GENERAL",
            modo_emision="ELECTRONICO",
            tipo_contribuyente_id="01",
            usuario_auditoria="test",
            activo=True,
        )
        session.add(company)
        session.flush()
        configured_tax = ImpuestoCatalogo(
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
        unconfigured_tax = ImpuestoCatalogo(
            tipo_impuesto=TipoImpuesto.IVA,
            codigo_tipo_impuesto="2",
            codigo_sri="4",
            descripcion="IVA 15% no configurado",
            vigente_desde=date(2020, 1, 1),
            aplica_a=AplicaA.AMBOS,
            porcentaje_iva=Decimal("15"),
            usuario_auditoria="test",
            activo=True,
        )
        session.add_all([configured_tax, unconfigured_tax])
        session.flush()
        company.impuesto_catalogo_ids = [str(configured_tax.id)]
        warehouse = Bodega(
            codigo_bodega="BA",
            nombre_bodega="Bodega A",
            empresa_id=company.id,
            usuario_auditoria="test",
            activo=True,
        )
        product = Producto(nombre="Shared", tipo=TipoProducto.BIEN, usuario_auditoria="test", activo=True)
        session.add_all([warehouse, product])
        session.flush()
        session.add_all(
            [
                ProductoBodega(producto_id=product.id, bodega_id=warehouse.id, cantidad=Decimal("0"), usuario_auditoria="test", activo=True),
                ProductoImpuesto(producto_id=product.id, empresa_id=company.id, impuesto_catalogo_id=configured_tax.id, codigo_impuesto_sri="2", codigo_porcentaje_sri="0", tarifa=Decimal("0"), usuario_auditoria="test", activo=True),
            ]
        )
        session.commit()

        token = set_current_company_id(str(company.id))
        try:
            with pytest.raises(Exception, match="no está configurado para la empresa"):
                ProductoService().update(
                    session,
                    product.id,
                    {"nombre": "No debe persistir", "impuesto_catalogo_ids": [unconfigured_tax.id]},
                )
        finally:
            reset_current_company_id(token)

        session.refresh(product)
        assignments = session.exec(
            select(ProductoImpuesto).where(
                ProductoImpuesto.producto_id == product.id,
                ProductoImpuesto.empresa_id == company.id,
                ProductoImpuesto.activo.is_(True),
            )
        ).all()
        assert product.nombre == "Shared"
        assert [row.impuesto_catalogo_id for row in assignments] == [configured_tax.id]
