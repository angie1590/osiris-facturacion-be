from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.atributo.entity import Atributo
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
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
            Atributo.__table__,
            Categoria.__table__,
            CategoriaAtributo.__table__,
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


def test_regla_b3_migra_productos_a_sin_clasificar_hermana_al_crear_hija():
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

        sin_clasificar = session.exec(
            select(Categoria)
            .where(Categoria.parent_id == categoria_a.id)
            .where(Categoria.is_default.is_(True))
        ).first()
        assert sin_clasificar is not None
        assert sin_clasificar.nombre == "Sin clasificar"
        assert sin_clasificar.parent_id == categoria_a.id
        assert sin_clasificar.is_default is True
        assert categoria_b.parent_id == sin_clasificar.parent_id

        rows_parent = session.exec(
            select(ProductoCategoria).where(ProductoCategoria.categoria_id == categoria_a.id)
        ).all()
        assert len(rows_parent) == 0

        rows_unclassified = session.exec(
            select(ProductoCategoria).where(ProductoCategoria.categoria_id == sin_clasificar.id)
        ).all()
        assert len(rows_unclassified) == 2
        assert {row.producto_id for row in rows_unclassified} == set(producto_ids)


def test_regla_b3_reutiliza_sin_clasificar_en_siguiente_hija():
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

        defaults = session.exec(
            select(Categoria)
            .where(Categoria.parent_id == categoria_a.id)
            .where(Categoria.is_default.is_(True))
        ).all()
        assert len(defaults) == 1
        assert defaults[0].nombre == "Sin clasificar"

        rows_parent = session.exec(
            select(ProductoCategoria).where(ProductoCategoria.categoria_id == categoria_a.id)
        ).all()
        assert len(rows_parent) == 0


def test_regla_b3_update_mueve_categoria_bajo_hoja_con_productos_y_migra_a_sin_clasificar():
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

        sin_clasificar = session.exec(
            select(Categoria)
            .where(Categoria.parent_id == categoria_x.id)
            .where(Categoria.is_default.is_(True))
        ).first()
        assert sin_clasificar is not None
        assert sin_clasificar.parent_id == updated.parent_id

        rows_x = session.exec(
            select(ProductoCategoria).where(ProductoCategoria.categoria_id == categoria_x.id)
        ).all()
        assert len(rows_x) == 0

        rows_unclassified = session.exec(
            select(ProductoCategoria).where(ProductoCategoria.categoria_id == sin_clasificar.id)
        ).all()
        assert len(rows_unclassified) == 2
        assert {row.producto_id for row in rows_unclassified} == set(producto_ids)


def test_bucket_sin_clasificar_se_desactiva_al_quedar_sin_productos_activos():
    engine = _build_test_engine()
    service = CategoriaService()

    with Session(engine) as session:
        parent = Categoria(
            nombre=f"Parent-{uuid4().hex[:6]}",
            es_padre=True,
            usuario_auditoria="test",
            activo=True,
        )
        bucket = Categoria(
            nombre="Sin clasificar",
            es_padre=False,
            is_default=True,
            parent_id=parent.id,
            usuario_auditoria="test",
            activo=True,
        )
        product = Producto(
            nombre=f"P-{uuid4().hex[:6]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            usuario_auditoria="test",
            activo=True,
        )
        session.add_all([parent, bucket, product])
        session.flush()
        session.add(ProductoCategoria(producto_id=product.id, categoria_id=bucket.id))
        session.commit()

        service.desactivar_defaults_vacios(session, {bucket.id})
        session.refresh(bucket)
        assert bucket.activo is True

        product.activo = False
        session.add(product)
        service.desactivar_defaults_vacios(session, {bucket.id})
        session.refresh(bucket)
        assert bucket.activo is False
