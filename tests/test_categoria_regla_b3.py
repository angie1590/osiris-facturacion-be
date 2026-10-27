from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.unidad.entity import Unidad
from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.atributo.entity import Atributo
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.inventario.categoria.service import CategoriaService
from osiris.modules.inventario.producto.entity import (
    Producto,
    ProductoCategoria,
    TipoProducto,
)
from osiris.modules.sri.impuesto_catalogo.entity import ImpuestoCatalogo


def _build_test_engine() -> Engine:
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
            Unidad.__table__,
            Atributo.__table__,
            Categoria.__table__,
            CategoriaAtributo.__table__,
            Producto.__table__,
            ProductoCategoria.__table__,
            ImpuestoCatalogo.__table__,
        ],
    )
    return engine


@pytest.mark.parametrize("operation", ["create", "rename", "move"])
def test_reject_duplicate_active_sibling_names(operation):
    with Session(_build_test_engine()) as session:
        parent = Categoria(nombre="Periféricos", es_padre=True)
        other_parent = Categoria(nombre="Otros", es_padre=True)
        session.add_all([parent, other_parent])
        session.flush()
        original = Categoria(nombre="Mouse", parent_id=parent.id)
        candidate = Categoria(
            nombre="Teclado" if operation == "rename" else "Mouse",
            parent_id=other_parent.id if operation == "move" else parent.id,
        )
        session.add(original)
        if operation != "create":
            session.add(candidate)
        session.commit()
        service = CategoriaService()
        with pytest.raises(HTTPException) as error:
            if operation == "create":
                service.create(
                    session,
                    {"nombre": " mouse ", "parent_id": parent.id, "es_padre": False},
                )
            elif operation == "rename":
                service.update(session, candidate.id, {"nombre": " MOUSE "})
            else:
                service.update(session, candidate.id, {"parent_id": parent.id})
        assert error.value.status_code == 409
        assert error.value.detail["code"] == "CATEGORY_DUPLICATE_NAME"


def test_category_names_allow_other_parents_but_reject_inactive_history_and_root_duplicates():
    with Session(_build_test_engine()) as session:
        service = CategoriaService()
        first = service.create(session, {"nombre": "Periféricos", "es_padre": True})
        second = service.create(session, {"nombre": "Accesorios", "es_padre": True})
        service.create(session, {"nombre": "Mouse", "parent_id": first.id})
        service.create(session, {"nombre": "Mouse", "parent_id": second.id})
        session.add(Categoria(nombre="Teclado", parent_id=first.id, activo=False))
        session.commit()
        with pytest.raises(HTTPException) as error:
            service.create(session, {"nombre": " teclado ", "parent_id": first.id})
        assert error.value.status_code == 409
        assert error.value.detail["code"] == "CATEGORY_DUPLICATE_NAME"
        assert error.value.detail["acciones_permitidas"] == ["reactivar", "renombrar"]
        created = service.create(session, {"nombre": "Teclado", "parent_id": second.id})
        service.update(session, created.id, {"nombre": "Teclado"})
        with pytest.raises(HTTPException) as error:
            service.create(session, {"nombre": " periféricos ", "es_padre": True})
        assert error.value.status_code == 409


def test_legacy_parent_flag_cannot_mark_a_leaf_as_parent():
    with Session(_build_test_engine()) as session:
        service = CategoriaService()
        category = service.create(
            session, {"nombre": "Hoja", "es_padre": True}
        )
        assert category.es_padre is False
        service.create(
            session,
            {"nombre": "Hija", "parent_id": category.id, "es_padre": False},
        )
        session.refresh(category)
        assert category.es_padre is True
        service.update(session, category.id, {"es_padre": False})
        session.refresh(category)
        assert category.es_padre is True


def test_reactivate_category_preserves_identity_and_independent_product_states():
    engine = _build_test_engine()
    with Session(engine) as session:
        category = Categoria(nombre="Historica", activo=False)
        product = Producto(
            nombre="Producto independiente",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            activo=False,
        )
        session.add_all([category, product])
        session.flush()
        assignment = ProductoCategoria(
            producto_id=product.id, categoria_id=category.id
        )
        session.add(assignment)
        session.commit()
        category_id = category.id
        assignment_id = assignment.id

        reactivated = CategoriaService().reactivate(session, category_id)

        assert reactivated is not None
        assert reactivated.id == category_id
        assert reactivated.activo is True
        assert session.get(Producto, product.id).activo is False
        assert session.get(ProductoCategoria, assignment_id) is not None
        events = session.exec(
            select(AuditLog).where(AuditLog.accion == "REACTIVATE_CATEGORY")
        ).all()
        assert len(events) == 1
    engine.dispose()


@pytest.mark.parametrize("operation", ["create", "update", "delete", "reactivate"])
def test_temporary_bucket_cannot_be_managed_manually(operation: str) -> None:
    engine = _build_test_engine()
    with Session(engine) as session:
        bucket = Categoria(
            nombre="Sin clasificar",
            is_default=True,
            activo=operation == "delete",
        )
        session.add(bucket)
        session.commit()
        service = CategoriaService()

        with pytest.raises(HTTPException) as error:
            if operation == "create":
                service.create(session, {"nombre": " sin CLASIFICAR "})
            elif operation == "update":
                service.update(session, bucket.id, {"nombre": "Temporal"})
            elif operation == "delete":
                service.delete(session, bucket.id)
            else:
                service.reactivate(session, bucket.id)

        assert error.value.status_code == 409
        assert error.value.detail["code"] == "CATEGORY_DEFAULT_PROTECTED"
        session.refresh(bucket)
        assert bucket.is_default is True
        assert bucket.activo is (operation == "delete")
    engine.dispose()


def _seed_categoria_hoja_con_dos_productos(
    session: Session,
) -> tuple[Categoria, list[UUID]]:
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
            confirmar_b3=True,
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
            select(ProductoCategoria).where(
                ProductoCategoria.categoria_id == categoria_a.id
            )
        ).all()
        assert len(rows_parent) == 0

        rows_unclassified = session.exec(
            select(ProductoCategoria).where(
                ProductoCategoria.categoria_id == sin_clasificar.id
            )
        ).all()
        assert len(rows_unclassified) == 2
        assert {row.producto_id for row in rows_unclassified} == set(producto_ids)


def test_regla_b3_requires_confirmation_before_reclassifying_products():
    engine = _build_test_engine()
    with Session(engine) as session:
        parent, product_ids = _seed_categoria_hoja_con_dos_productos(session)
        with pytest.raises(HTTPException) as error:
            CategoriaService().create(
                session,
                {"nombre": "New child", "parent_id": parent.id},
            )
        assert error.value.status_code == 409
        assert error.value.detail["code"] == "CATEGORY_CHANGE_REQUIRES_CONFIRMATION"
        assert error.value.detail["conteos"]["productos_directos"] == 2
        assert error.value.detail["acciones_permitidas"] == ["previsualizar"]
        assert not session.exec(
            select(Categoria).where(Categoria.parent_id == parent.id)
        ).all()
        assignments = session.exec(
            select(ProductoCategoria).where(
                ProductoCategoria.producto_id.in_(product_ids)
            )
        ).all()
        assert all(assignment.categoria_id == parent.id for assignment in assignments)


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
            confirmar_b3=True,
        )
        service.create(
            session,
            {
                "nombre": f"C-{uuid4().hex[:6]}",
                "es_padre": False,
                "parent_id": categoria_a.id,
                "usuario_auditoria": "test",
            },
            confirmar_b3=True,
        )

        defaults = session.exec(
            select(Categoria)
            .where(Categoria.parent_id == categoria_a.id)
            .where(Categoria.is_default.is_(True))
        ).all()
        assert len(defaults) == 1
        assert defaults[0].nombre == "Sin clasificar"

        rows_parent = session.exec(
            select(ProductoCategoria).where(
                ProductoCategoria.categoria_id == categoria_a.id
            )
        ).all()
        assert len(rows_parent) == 0


@pytest.mark.parametrize("operation", ["create", "move"])
@pytest.mark.parametrize("commit", [False, True])
def test_regla_b3_reutiliza_bucket_inactivo_y_respeta_unidad_de_trabajo(operation, commit):
    with Session(_build_test_engine()) as session:
        parent, product_ids = _seed_categoria_hoja_con_dos_productos(session)
        parent_id = parent.id
        bucket = Categoria(
            nombre="Sin clasificar",
            parent_id=parent_id,
            is_default=True,
            activo=False,
            usuario_auditoria="original",
        )
        candidate = Categoria(nombre="Candidate")
        session.add_all([bucket, candidate])
        session.commit()
        bucket_id, candidate_id = bucket.id, candidate.id
        original_audit_ids = {row.id for row in session.exec(select(AuditLog)).all()}
        service = CategoriaService()
        if operation == "create":
            child = service.create(
                session,
                {"nombre": "New child", "parent_id": parent_id},
                commit=commit,
                confirmar_b3=True,
            )
        else:
            child = service.update(
                session,
                candidate_id,
                {"parent_id": parent_id},
                commit=commit,
                confirmar_b3=True,
            )
        assert child is not None
        child_id = child.id
        defaults = session.exec(
            select(Categoria)
            .where(Categoria.parent_id == parent_id, Categoria.is_default.is_(True))
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        ).all()
        assert [(row.id, row.activo) for row in defaults] == [(bucket_id, True)]
        assert defaults[0].created_by == "original"
        links = session.exec(
            select(ProductoCategoria).where(ProductoCategoria.categoria_id == bucket_id)
        ).all()
        assert {link.producto_id for link in links} == set(product_ids)
        events = session.exec(
            select(AuditLog).where(AuditLog.accion == "CATEGORY_B3_REACTIVATE")
        ).all()
        assert len(events) == 1
        assert events[0].entidad_id == bucket_id
        assert events[0].before_json == {"activo": False}
        assert events[0].after_json["activo"] is True

        session.rollback()
        historical_bucket = session.exec(
            select(Categoria)
            .where(Categoria.id == bucket_id)
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        ).one()
        assert historical_bucket.activo is commit
        if not commit:
            assert historical_bucket.usuario_auditoria == "original"
            assert session.get(Categoria, parent_id).es_padre is False
            if operation == "create":
                assert session.get(Categoria, child_id) is None
            else:
                assert session.get(Categoria, candidate_id).parent_id is None
            links = session.exec(
                select(ProductoCategoria).where(ProductoCategoria.categoria_id == parent_id)
            ).all()
            assert {link.producto_id for link in links} == set(product_ids)
            assert {row.id for row in session.exec(select(AuditLog)).all()} == original_audit_ids


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
            confirmar_b3=True,
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
            select(ProductoCategoria).where(
                ProductoCategoria.categoria_id == categoria_x.id
            )
        ).all()
        assert len(rows_x) == 0

        rows_unclassified = session.exec(
            select(ProductoCategoria).where(
                ProductoCategoria.categoria_id == sin_clasificar.id
            )
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
        event = session.exec(
            select(AuditLog).where(
                AuditLog.entidad_id == bucket.id,
                AuditLog.accion == "CATEGORY_B3_DEACTIVATE",
            )
        ).first()
        assert event is not None
