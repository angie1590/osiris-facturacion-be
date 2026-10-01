from __future__ import annotations

from decimal import Decimal

from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.producto.entity import Producto, ProductoCategoria, TipoProducto
from osiris.modules.inventario.producto.service import ProductoService


def test_light_product_listing_includes_categories_for_bulk_selection():
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
        ],
    )

    with Session(engine) as session:
        category = Categoria(nombre="Bebidas", es_padre=False, activo=True, usuario_auditoria="tester")
        product = Producto(
            nombre="Cerveza artesanal",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("2.50"),
            usuario_auditoria="tester",
            activo=True,
        )
        session.add(category)
        session.add(product)
        session.flush()
        session.add(ProductoCategoria(producto_id=product.id, categoria_id=category.id))
        session.commit()

        rows, meta = ProductoService().list_paginated_completo(
            session,
            only_active=True,
            limit=6,
            offset=0,
        )

        assert meta.total == 1
        assert rows[0]["categorias"] == [{"id": category.id, "nombre": "Bebidas"}]
