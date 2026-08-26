from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria.service import CategoriaService
from osiris.modules.inventario.producto.entity import Producto, ProductoCategoria, TipoProducto
from osiris.modules.sri.impuesto_catalogo.entity import ImpuestoCatalogo


def _build_test_engine():
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
            ImpuestoCatalogo.__table__,
        ],
    )
    return engine


def _seed_categoria_hoja_con_dos_productos(session: Session) -> tuple[Categoria, list[UUID]]:
    categoria_a = Categoria(
        nombre=f"A-{uuid4().hex[:6]}",
        es_padre=False,
        usuario_auditoria="test",
        activo=True,
    )
    producto_1 = Producto(
        nombre=f"P1-{uuid4().hex[:6]}",
        tipo=TipoProducto.BIEN,
        pvp=Decimal("10.00"),
        usuario_auditoria="test",
        activo=True,
    )
    producto_2 = Producto(
        nombre=f"P2-{uuid4().hex[:6]}",
        tipo=TipoProducto.BIEN,
        pvp=Decimal("20.00"),
        usuario_auditoria="test",
        activo=True,
    )

    session.add_all([categoria_a, producto_1, producto_2])
    session.flush()

    session.add_all(
        [
            ProductoCategoria(producto_id=producto_1.id, categoria_id=categoria_a.id),
            ProductoCategoria(producto_id=producto_2.id, categoria_id=categoria_a.id),
        ]
    )
    session.commit()
    session.refresh(categoria_a)
    return categoria_a, [producto_1.id, producto_2.id]


def test_regla_b3_migra_productos_a_general_al_crear_hija():
    engine = _build_test_engine()
    service = CategoriaService()

    with Session(engine) as session:
        categoria_a, producto_ids = _seed_categoria_hoja_con_dos_productos(session)

        categoria_b = service.create(
            session,
            {
                "nombre": f"B-{uuid4().hex[:6]}",
                "es_padre": False,
                "parent_id": categoria_a.id,
                "usuario_auditoria": "test",
            },
        )
        assert categoria_b.parent_id == categoria_a.id

        categoria_a_db = session.get(Categoria, categoria_a.id)
        assert categoria_a_db is not None
        assert categoria_a_db.es_padre is True

        general = session.exec(
            select(Categoria)
            .where(Categoria.parent_id == categoria_a.id)
            .where(func.lower(Categoria.nombre) == "general")
        ).first()
        assert general is not None

        rows_parent = session.exec(
            select(ProductoCategoria).where(ProductoCategoria.categoria_id == categoria_a.id)
        ).all()
        assert len(rows_parent) == 0

        rows_general = session.exec(
            select(ProductoCategoria).where(ProductoCategoria.categoria_id == general.id)
        ).all()
        assert len(rows_general) == 2
        assert {row.producto_id for row in rows_general} == set(producto_ids)


def test_regla_b3_reutiliza_general_existente_en_siguiente_hija():
    engine = _build_test_engine()
    service = CategoriaService()

    with Session(engine) as session:
        categoria_a, _ = _seed_categoria_hoja_con_dos_productos(session)

        service.create(
            session,
            {
                "nombre": f"B-{uuid4().hex[:6]}",
                "es_padre": False,
                "parent_id": categoria_a.id,
                "usuario_auditoria": "test",
            },
        )
        service.create(
            session,
            {
                "nombre": f"C-{uuid4().hex[:6]}",
                "es_padre": False,
                "parent_id": categoria_a.id,
                "usuario_auditoria": "test",
            },
        )

        generals = session.exec(
            select(Categoria)
            .where(Categoria.parent_id == categoria_a.id)
            .where(func.lower(Categoria.nombre) == "general")
        ).all()
        assert len(generals) == 1

        rows_parent = session.exec(
            select(ProductoCategoria).where(ProductoCategoria.categoria_id == categoria_a.id)
        ).all()
        assert len(rows_parent) == 0


def test_regla_b3_update_mueve_categoria_bajo_hoja_con_productos_y_migra_a_general():
    engine = _build_test_engine()
    service = CategoriaService()

    with Session(engine) as session:
        categoria_x, producto_ids = _seed_categoria_hoja_con_dos_productos(session)
        categoria_y = Categoria(
            nombre=f"Y-{uuid4().hex[:6]}",
            es_padre=False,
            parent_id=None,
            usuario_auditoria="test",
            activo=True,
        )
        session.add(categoria_y)
        session.commit()
        session.refresh(categoria_y)

        updated = service.update(
            session,
            categoria_y.id,
            {
                "parent_id": categoria_x.id,
                "usuario_auditoria": "test",
            },
        )
        assert updated is not None
        assert updated.parent_id == categoria_x.id

        categoria_x_db = session.get(Categoria, categoria_x.id)
        assert categoria_x_db is not None
        assert categoria_x_db.es_padre is True

        general = session.exec(
            select(Categoria)
            .where(Categoria.parent_id == categoria_x.id)
            .where(func.lower(Categoria.nombre) == "general")
        ).first()
        assert general is not None

        rows_x = session.exec(
            select(ProductoCategoria).where(ProductoCategoria.categoria_id == categoria_x.id)
        ).all()
        assert len(rows_x) == 0

        rows_general = session.exec(
            select(ProductoCategoria).where(ProductoCategoria.categoria_id == general.id)
        ).all()
        assert len(rows_general) == 2
        assert {row.producto_id for row in rows_general} == set(producto_ids)
