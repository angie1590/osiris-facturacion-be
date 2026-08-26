from __future__ import annotations

from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy import Column, Table
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from osiris.modules.inventario.producto.models_atributos import ProductoAtributoValor


def _engine_sqlite():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def _ensure_fk_targets_in_metadata() -> None:
    """
    Garantiza que los targets de FK existan en metadata para poder crear
    la tabla de prueba sin depender del esquema completo.
    """
    if "tbl_producto" not in SQLModel.metadata.tables:
        Table(
            "tbl_producto",
            SQLModel.metadata,
            Column("id", sa.Uuid(), primary_key=True),
        )
    if "tbl_atributo" not in SQLModel.metadata.tables:
        Table(
            "tbl_atributo",
            SQLModel.metadata,
            Column("id", sa.Uuid(), primary_key=True),
        )


def _create_table_under_test(engine) -> None:
    _ensure_fk_targets_in_metadata()
    ProductoAtributoValor.__table__.create(bind=engine, checkfirst=True)


def test_producto_atributo_valor_check_constraint_falla_por_doble_valor():
    engine = _engine_sqlite()
    _create_table_under_test(engine)

    with Session(engine) as session:
        session.add(
            ProductoAtributoValor(
                producto_id=uuid4(),
                atributo_id=uuid4(),
                valor_string="Hola",
                valor_integer=10,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_producto_atributo_valor_check_constraint_falla_por_todos_nulos():
    engine = _engine_sqlite()
    _create_table_under_test(engine)

    with Session(engine) as session:
        session.add(
            ProductoAtributoValor(
                producto_id=uuid4(),
                atributo_id=uuid4(),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_producto_atributo_valor_unique_constraint_falla_por_duplicidad():
    engine = _engine_sqlite()
    _create_table_under_test(engine)

    producto_id = uuid4()
    atributo_id = uuid4()

    with Session(engine) as session:
        session.add(
            ProductoAtributoValor(
                producto_id=producto_id,
                atributo_id=atributo_id,
                valor_string="rojo",
            )
        )
        session.commit()

        session.add(
            ProductoAtributoValor(
                producto_id=producto_id,
                atributo_id=atributo_id,
                valor_integer=10,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
