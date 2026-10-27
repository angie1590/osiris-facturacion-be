from __future__ import annotations

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from uuid import uuid4

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlmodel import Session, col, select

from osiris.core.catalog_lock import CATALOG_MUTATION_LOCK_KEY
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria.service import CategoriaService
from osiris.modules.inventario.producto.entity import ProductoCategoria
from osiris.modules.inventario.producto.service import ProductoService


def _product_stub(metadata: sa.MetaData) -> sa.Table:
    return sa.Table(
        "tbl_producto",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
    )


@pytest.fixture
def postgresql_catalog_engine() -> Iterator[sa.Engine]:
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
    schema = "category_hierarchy_test_" + uuid4().hex
    with admin.begin() as connection:
        connection.execute(sa.schema.CreateSchema(schema))
    engine = admin.execution_options(schema_translate_map={None: schema})
    metadata = sa.MetaData()
    _product_stub(metadata)
    for model in (Categoria, ProductoCategoria, AuditLog):
        source = sa.inspect(model).local_table
        assert isinstance(source, sa.Table)
        source.to_metadata(metadata)
    try:
        metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(sa.schema.DropSchema(schema, cascade=True))
        admin.dispose()


def test_postgres_child_creation_serializes_with_product_leaf_validation(
    postgresql_catalog_engine: sa.Engine,
) -> None:
    engine = postgresql_catalog_engine
    with Session(engine) as session:
        parent = Categoria(nombre="Parent", activo=True, es_padre=False)
        session.add(parent)
        session.commit()
        parent_id = parent.id

    child_created = Event()
    classifier_attempted_lock = Event()

    def create_child() -> None:
        with Session(engine) as session, session.begin():
            CategoriaService().create(
                session,
                {"nombre": "Child", "parent_id": parent_id},
                commit=False,
            )
            child_created.set()
            assert classifier_attempted_lock.wait(timeout=5)

    def validate_product_category() -> tuple[int, str]:
        assert child_created.wait(timeout=5)
        with Session(engine) as session, session.begin():
            owns_lock = session.execute(
                sa.text("SELECT pg_try_advisory_xact_lock(:key)"),
                {"key": CATALOG_MUTATION_LOCK_KEY},
            ).scalar_one()
            assert owns_lock is False
            classifier_attempted_lock.set()
            CategoriaService.acquire_hierarchy_mutation_lock(session)
            with pytest.raises(HTTPException) as error:
                ProductoService()._validate_leaf_categories(session, [parent_id])
            return error.value.status_code, str(error.value.detail)

    with ThreadPoolExecutor(max_workers=2) as executor:
        child_future = executor.submit(create_child)
        classification_future = executor.submit(validate_product_category)
        child_future.result(timeout=10)
        status_code, detail = classification_future.result(timeout=10)

    assert status_code == 400
    assert "hoja" in detail.lower()
    with Session(engine) as session:
        child = session.exec(
            select(Categoria).where(Categoria.parent_id == parent_id)
        ).one()
        assert child.nombre == "Child"
        persisted_parent = session.get(Categoria, parent_id)
        assert persisted_parent is not None and persisted_parent.es_padre is True


def test_postgres_concurrent_children_reactivate_one_historical_b3_bucket(
    postgresql_catalog_engine: sa.Engine,
) -> None:
    engine = postgresql_catalog_engine
    with Session(engine) as session:
        parent = Categoria(nombre="Parent", activo=True, es_padre=False)
        bucket = Categoria(
            nombre="Sin clasificar",
            parent_id=None,
            is_default=True,
            activo=False,
        )
        session.add_all([parent, bucket])
        session.flush()
        bucket.parent_id = parent.id
        product_id = uuid4()
        session.execute(_product_stub(sa.MetaData()).insert().values(id=product_id))
        session.add(ProductoCategoria(producto_id=product_id, categoria_id=parent.id))
        session.commit()
        parent_id, bucket_id = parent.id, bucket.id

    ready = Barrier(2)

    def create_child(name: str) -> None:
        ready.wait(timeout=5)
        with Session(engine) as session:
            CategoriaService().create(
                session,
                {"nombre": name, "parent_id": parent_id},
                confirmar_b3=True,
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(create_child, "Child A")
        second = executor.submit(create_child, "Child B")
        first.result(timeout=10)
        second.result(timeout=10)

    with Session(engine) as session:
        buckets = session.exec(
            select(Categoria)
            .where(Categoria.parent_id == parent_id)
            .where(col(Categoria.is_default).is_(True))
            .execution_options(**{"soft_delete_include_inactive": True})
        ).all()
        assert len(buckets) == 1
        assert buckets[0].id == bucket_id and buckets[0].activo is True
        relation = session.exec(
            select(ProductoCategoria).where(ProductoCategoria.producto_id == product_id)
        ).one()
        assert relation.categoria_id == bucket_id
