from __future__ import annotations

from collections.abc import Callable, Generator
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import Table, UniqueConstraint
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.engine import Dialect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateIndex
from sqlmodel import Session, select

from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.inventario.atributo.entity import Atributo, TipoDato
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria.repository import CategoriaRepository
from osiris.modules.inventario.categoria.service import CategoriaService
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.inventario.categoria_atributo.models import CategoriaAtributoCreate
from osiris.modules.inventario.categoria_atributo.service import CategoriaAtributoService
from tests.test_categoria_regla_b3 import _build_test_engine


class _PostgresIntegrityError(Exception):
    def __init__(self, constraint: str) -> None:
        super().__init__("database error")
        self.diag = SimpleNamespace(constraint_name=constraint)


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = _build_test_engine()
    with Session(engine) as database_session:
        yield database_session
    engine.dispose()


@pytest.mark.parametrize("dialect_factory", [postgresql.dialect, sqlite.dialect])
def test_orm_declares_exact_historical_identity_constraints(
    dialect_factory: Callable[[], Dialect],
) -> None:
    category_table = cast(Table, getattr(Categoria, "__table__"))
    assignment_table = cast(Table, getattr(CategoriaAtributo, "__table__"))
    indices = {str(index.name): index for index in category_table.indexes}
    for scope, columns, predicate in (
        ("root", "lower(trim(nombre))", "parent_id IS NULL"),
        ("child", "parent_id, lower(trim(nombre))", "parent_id IS NOT NULL"),
    ):
        name = f"uq_tbl_categoria_{scope}_nombre_historical"
        statement = str(CreateIndex(indices[name]).compile(dialect=dialect_factory()))
        expression = (
            "lower(trim(nombre))"
            if dialect_factory is sqlite.dialect
            else "lower(TRIM(BOTH FROM nombre))"
        )
        assert statement == f"CREATE UNIQUE INDEX {name} ON tbl_categoria ({columns.replace('lower(trim(nombre))', expression)}) WHERE {predicate}"
    constraints = [
        constraint
        for constraint in assignment_table.constraints
        if isinstance(constraint, UniqueConstraint)
    ]
    assert [(constraint.name, list(constraint.columns.keys())) for constraint in constraints] == [
        ("uq_categoria_atributo_historical", ["categoria_id", "atributo_id"])
    ]


@pytest.mark.parametrize("parent", [False, True])
@pytest.mark.parametrize("inactive", [False, True])
def test_category_rejects_historical_name_with_global_soft_delete(
    session: Session, parent: bool, inactive: bool
) -> None:
    parent_category = Categoria(nombre="Parent")
    session.add(parent_category)
    session.flush()
    parent_id = parent_category.id if parent else None
    original = Categoria(nombre="Mouse", parent_id=parent_id, activo=not inactive)
    session.add(original)
    session.commit()
    with pytest.raises(HTTPException) as error:
        CategoriaService().create(session, {"nombre": " MOUSE ", "parent_id": parent_id})
    assert error.value.status_code == 409
    assert error.value.detail == CategoriaRepository.duplicate_name().detail
    rows = session.exec(
        select(Categoria).execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
    ).all()
    assert len(rows) == 2
    stored = session.get(Categoria, original.id)
    assert stored is not None
    assert stored.activo is not inactive


@pytest.mark.parametrize("scope", ["root", "child"])
@pytest.mark.parametrize("diagnostic", [False, True])
def test_category_repository_translates_both_index_errors(scope: str, diagnostic: bool) -> None:
    name = f"uq_tbl_categoria_{scope}_nombre_historical"
    original = _PostgresIntegrityError(name) if diagnostic else Exception(name)
    error = IntegrityError("INSERT", {}, original)
    with pytest.raises(HTTPException) as raised:
        CategoriaRepository()._raise_integrity(error)
    assert raised.value.status_code == 409
    assert raised.value.detail == CategoriaRepository.duplicate_name().detail
    assert raised.value.__cause__ is error


@pytest.mark.parametrize("parent", [False, True])
def test_category_race_rolls_back_and_returns_canonical_error(
    session: Session, parent: bool
) -> None:
    parent_category = Categoria(nombre="Parent")
    session.add(parent_category)
    session.flush()
    parent_id = parent_category.id if parent else None
    session.add(Categoria(nombre="Mouse", parent_id=parent_id, activo=False))
    session.commit()
    service = CategoriaService()
    with patch.object(service, "_validate_sibling_name"), pytest.raises(HTTPException) as error:
        service.create(session, {"nombre": " mouse ", "parent_id": parent_id})
    assert error.value.detail == CategoriaRepository.duplicate_name().detail
    assert session.is_active
    assert not session.exec(select(AuditLog)).all()


def _seed_assignment(session: Session, active: bool) -> CategoriaAtributo:
    category = Categoria(nombre="Category")
    attribute = Atributo(
        nombre="Attribute", codigo="identity_attribute", tipo_dato=TipoDato.STRING
    )
    session.add_all([category, attribute])
    session.flush()
    assignment = CategoriaAtributo(
        categoria_id=category.id, atributo_id=attribute.id, activo=active
    )
    session.add(assignment)
    session.commit()
    return assignment


@pytest.mark.parametrize("active", [False, True])
@pytest.mark.parametrize("commit", [False, True])
def test_mapping_rejects_existing_identity_without_new_row(
    session: Session, active: bool, commit: bool
) -> None:
    assignment = _seed_assignment(session, active)
    original_id = assignment.id
    dto = CategoriaAtributoCreate(
        categoria_id=assignment.categoria_id, atributo_id=assignment.atributo_id
    )
    with pytest.raises(HTTPException) as error:
        CategoriaAtributoService().create(session, dto, commit=commit)
    assert error.value.status_code == 409
    assert isinstance(error.value.detail, dict)
    assert error.value.detail["code"] == "ATTRIBUTE_ALREADY_ASSIGNED"
    assert "reactivar" in error.value.detail["acciones_permitidas"]
    rows = session.exec(
        select(CategoriaAtributo).execution_options(
            **{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True}
        )
    ).all()
    assert [(row.id, row.activo) for row in rows] == [(original_id, active)]
    assert not session.exec(select(AuditLog)).all()


@pytest.mark.parametrize("active", [False, True])
@pytest.mark.parametrize("commit", [False, True])
def test_mapping_race_translates_constraint_and_respects_outer_rollback(
    session: Session, active: bool, commit: bool
) -> None:
    assignment = _seed_assignment(session, active)
    dto = CategoriaAtributoCreate(
        categoria_id=assignment.categoria_id, atributo_id=assignment.atributo_id
    )
    pending = Categoria(nombre="Outer pending category")
    session.add(pending)
    session.flush()
    pending_id = pending.id
    service = CategoriaAtributoService()
    with (
        patch.object(service, "_validar_asignacion_historica"),
        patch.object(session, "rollback", wraps=session.rollback) as rollback,
        pytest.raises(HTTPException) as error,
    ):
        service.create(session, dto, commit=commit)
    assert error.value.status_code == 409
    assert isinstance(error.value.detail, dict)
    assert error.value.detail["code"] == "ATTRIBUTE_ALREADY_ASSIGNED"
    assert isinstance(error.value.__cause__, IntegrityError)
    assert rollback.call_count == int(commit)
    if not commit:
        assert not session.is_active
        session.rollback()
    assert session.is_active
    assert session.get(Categoria, pending_id) is None
    assert not session.exec(select(AuditLog)).all()


def test_mapping_commit_false_flushes_without_committing_outer_work(session: Session) -> None:
    category = Categoria(nombre="Pending category")
    attribute = Atributo(
        nombre="Pending attribute", codigo="pending_attribute", tipo_dato=TipoDato.STRING
    )
    session.add_all([category, attribute])
    session.flush()
    category_id, attribute_id = category.id, attribute.id
    dto = CategoriaAtributoCreate(categoria_id=category_id, atributo_id=attribute_id)
    with patch.object(session, "commit", wraps=session.commit) as commit:
        created = CategoriaAtributoService().create(session, dto, commit=False)
    assert commit.call_count == 0
    assert session.exec(select(CategoriaAtributo.id)).one() == created.id
    assert len(session.exec(select(AuditLog)).all()) == 1
    session.rollback()
    assert session.get(Categoria, category_id) is None
    assert session.get(Atributo, attribute_id) is None
    assert not session.exec(select(CategoriaAtributo)).all()
    assert not session.exec(select(AuditLog)).all()


def test_mapping_postgresql_constraint_translation_leaves_other_integrity_errors_intact() -> None:
    for name in ("uq_categoria_atributo_historical", "unrelated_foreign_key"):
        original = _PostgresIntegrityError(name)
        error = IntegrityError("INSERT", {}, original)
        if name == "uq_categoria_atributo_historical":
            with pytest.raises(HTTPException) as raised:
                CategoriaAtributoService._raise_integrity(error)
            assert isinstance(raised.value.detail, dict)
            assert raised.value.detail["code"] == "ATTRIBUTE_ALREADY_ASSIGNED"
        else:
            with pytest.raises(IntegrityError) as unrelated:
                CategoriaAtributoService._raise_integrity(error)
            assert unrelated.value is error