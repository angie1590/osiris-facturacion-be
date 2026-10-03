from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria.service import CategoriaService
from osiris.modules.inventario.movimientos.models import InventarioStock
from osiris.modules.inventario.producto.entity import Producto, ProductoCategoria, TipoProducto
from osiris.modules.sri.impuesto_catalogo.entity import ImpuestoCatalogo


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
            CasaComercial.__table__,
            Categoria.__table__,
            Producto.__table__,
            ProductoCategoria.__table__,
            InventarioStock.__table__,
            ImpuestoCatalogo.__table__,
        ],
    )
    return engine


def _category_product(session: Session, *, stock: Decimal = Decimal("0")):
    category = Categoria(
        nombre=f"Categoria-{uuid4().hex[:6]}",
        es_padre=False,
        usuario_auditoria="test",
        activo=True,
    )
    product = Producto(
        nombre=f"Producto-{uuid4().hex[:6]}",
        tipo=TipoProducto.BIEN,
        pvp=Decimal("10.00"),
        cantidad=stock,
        usuario_auditoria="test",
        activo=True,
    )
    session.add_all([category, product])
    session.flush()
    session.add(ProductoCategoria(producto_id=product.id, categoria_id=category.id))
    session.commit()
    return category, product


def test_category_delete_blocks_active_children():
    engine = _engine()
    with Session(engine) as session:
        parent = Categoria(nombre="Padre", es_padre=True, usuario_auditoria="test", activo=True)
        session.add(parent)
        session.flush()
        session.add(Categoria(nombre="Hijo", es_padre=False, parent_id=parent.id, usuario_auditoria="test", activo=True))
        session.commit()

        with pytest.raises(HTTPException) as exc_info:
            CategoriaService().delete(session, parent.id, confirmar_baja_productos=True)

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["code"] == "CATEGORY_HAS_ACTIVE_CHILDREN"
        assert session.get(Categoria, parent.id).activo is True


def test_category_delete_blocks_positive_stock_even_with_confirmation():
    engine = _engine()
    with Session(engine) as session:
        category, product = _category_product(session)
        session.add(
            InventarioStock(
                bodega_id=uuid4(),
                producto_id=product.id,
                cantidad_actual=Decimal("1.0000"),
                costo_promedio_vigente=Decimal("0.0000"),
                usuario_auditoria="test",
                activo=True,
            )
        )
        session.commit()

        with pytest.raises(HTTPException) as exc_info:
            CategoriaService().delete(session, category.id, confirmar_baja_productos=True)

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["code"] == "CATEGORY_PRODUCTS_HAVE_STOCK"
        assert session.get(Producto, product.id).activo is True
        assert session.get(Categoria, category.id).activo is True


def test_category_delete_requires_confirmation_then_cascades_without_stock():
    engine = _engine()
    with Session(engine) as session:
        parent = Categoria(nombre="Parent", es_padre=True, usuario_auditoria="test", activo=True)
        session.add(parent)
        session.flush()
        category, product = _category_product(session)
        category.parent_id = parent.id
        session.add(category)
        session.commit()

        with pytest.raises(HTTPException) as exc_info:
            CategoriaService().delete(session, category.id)

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["code"] == "CATEGORY_PRODUCTS_REQUIRE_CONFIRMATION"
        assert session.get(Producto, product.id).activo is True

        assert CategoriaService().delete(session, category.id, confirmar_baja_productos=True) is True

        session.refresh(category)
        session.refresh(product)
        session.refresh(parent)
        assert category.activo is False
        assert product.activo is False
        assert parent.es_padre is False
