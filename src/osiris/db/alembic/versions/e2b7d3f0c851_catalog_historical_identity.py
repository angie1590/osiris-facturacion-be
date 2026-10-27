"""Enforce historical catalog identities and reconcile the legacy parent projection."""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

revision = "e2b7d3f0c851"
down_revision = "e1a6c2d9b740"
branch_labels = None
depends_on = None


def _preflight(connection: Connection) -> None:
    errors: list[str] = []
    for table, columns, predicate, code in (
        ("tbl_categoria", "parent_id, lower(trim(nombre))", "true", "CATEGORY_DUPLICATE_NAME"),
        ("tbl_categoria_atributo", "categoria_id, atributo_id", "true",
         "CATEGORY_ATTRIBUTE_DUPLICATE"),
        ("tbl_atributo", "lower(trim(nombre))", "activo = true", "ATTRIBUTE_DUPLICATE_NAME"),
        ("tbl_atributo", "lower(codigo)", "true", "ATTRIBUTE_DUPLICATE_CODE"),
    ):
        duplicate = connection.execute(sa.text(
            f"SELECT {columns} FROM {table} WHERE {predicate} "
            f"GROUP BY {columns} HAVING count(*) > 1"
        )).all()
        if duplicate:
            ids = connection.execute(sa.text(f"SELECT id FROM {table} ORDER BY id")).scalars()
            errors.append(f"{code}: keys={duplicate!r}, inspect ids={list(map(str, ids))}")
    categories = {row["id"]: row for row in connection.execute(sa.text(
        "SELECT id, parent_id, activo, is_default FROM tbl_categoria"
    )).mappings()}
    active_parents = {row["parent_id"] for row in categories.values() if row["activo"]}
    for category_id, row in categories.items():
        parent_id = row["parent_id"]
        parent = categories.get(parent_id)
        if parent_id is not None and (
            parent is None or (row["activo"] and not parent["activo"])
        ):
            errors.append(f"CATEGORY_PARENT_INVALID: id={category_id}, parent_id={parent_id}")
        if row["is_default"] and (
            parent is None or parent["is_default"] or category_id in active_parents
        ):
            errors.append(f"CATEGORY_DEFAULT_INVALID: id={category_id}")
        visited: set[Any] = set()
        current = category_id
        while current in categories:
            if current in visited:
                errors.append(f"CATEGORY_CYCLE: ids={list(map(str, visited))}")
                break
            visited.add(current)
            current = categories[current]["parent_id"]
    invalid = connection.execute(sa.text(
        "SELECT mapping.id FROM tbl_categoria_atributo AS mapping "
        "LEFT JOIN tbl_categoria AS category ON category.id = mapping.categoria_id "
        "LEFT JOIN tbl_atributo AS attribute ON attribute.id = mapping.atributo_id "
        "WHERE category.id IS NULL OR attribute.id IS NULL"
    )).scalars().all()
    if invalid:
        errors.append(f"CATEGORY_ATTRIBUTE_REFERENCE_INVALID: ids={list(map(str, invalid))}")
    if errors:
        raise RuntimeError(
            "Catalog preflight blocked before DDL. Resolve conflicts explicitly; "
            "no merge or arbitrary survivor is permitted:\n" + "\n".join(errors)
        )


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        connection.execute(sa.text(
            "LOCK TABLE tbl_atributo, tbl_categoria, tbl_categoria_atributo "
            "IN SHARE ROW EXCLUSIVE MODE"
        ))
    _preflight(connection)
    with op.batch_alter_table("tbl_categoria_atributo") as batch:
        batch.create_unique_constraint("uq_categoria_atributo_historical",
                                       ["categoria_id", "atributo_id"])
    op.create_index(
        "uq_tbl_categoria_root_nombre_historical", "tbl_categoria",
        [sa.text("lower(trim(nombre))")], unique=True,
        sqlite_where=sa.text("parent_id IS NULL"), postgresql_where=sa.text("parent_id IS NULL"),
    )
    op.create_index(
        "uq_tbl_categoria_child_nombre_historical", "tbl_categoria",
        ["parent_id", sa.text("lower(trim(nombre))")], unique=True,
        sqlite_where=sa.text("parent_id IS NOT NULL"),
        postgresql_where=sa.text("parent_id IS NOT NULL"),
    )
    connection.execute(sa.text(
        "UPDATE tbl_categoria SET es_padre = EXISTS ("
        "SELECT 1 FROM tbl_categoria AS child "
        "WHERE child.parent_id = tbl_categoria.id AND child.activo = true)"
    ))


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        connection.execute(sa.text(
            "LOCK TABLE tbl_atributo, tbl_categoria, tbl_categoria_atributo, tbl_atributo_cambio "
            "IN SHARE ROW EXCLUSIVE MODE"
        ))
    for table in ("tbl_categoria", "tbl_atributo", "tbl_categoria_atributo", "tbl_atributo_cambio"):
        if connection.execute(sa.text(f"SELECT id FROM {table} LIMIT 1")).first():
            raise RuntimeError(
                f"Cannot downgrade: {table} contains catalog history whose identity "
                "guarantees would be lost. Preserve the schema for operational rollback."
            )
    op.drop_index("uq_tbl_categoria_child_nombre_historical", table_name="tbl_categoria")
    op.drop_index("uq_tbl_categoria_root_nombre_historical", table_name="tbl_categoria")
    with op.batch_alter_table("tbl_categoria_atributo") as batch:
        batch.drop_constraint("uq_categoria_atributo_historical", type_="unique")