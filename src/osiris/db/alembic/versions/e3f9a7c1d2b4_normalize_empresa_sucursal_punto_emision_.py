"""normalize empresa/sucursal/punto emision hierarchy

Revision ID: e3f9a7c1d2b4
Revises: d4e5f6a7b8c9
Create Date: 2026-02-22 10:30:00.000000
"""

from __future__ import annotations

from datetime import datetime
from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e3f9a7c1d2b4"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table_name)}


def _table_clause(table_name: str) -> sa.Table:
    columns = [sa.column(column_name) for column_name in _table_columns(table_name)]
    return sa.table(table_name, *columns)


def _drop_fk_for_column(table_name: str, column_name: str) -> None:
    inspector = sa.inspect(op.get_bind())
    for fk in inspector.get_foreign_keys(table_name):
        if column_name in fk.get("constrained_columns", []) and fk.get("name"):
            op.drop_constraint(fk["name"], table_name, type_="foreignkey")


def _drop_unique_if_exists(table_name: str, constraint_name: str) -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {constraint["name"] for constraint in inspector.get_unique_constraints(table_name)}
    if constraint_name in existing:
        op.drop_constraint(constraint_name, table_name, type_="unique")


def _unique_exists(table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return constraint_name in {
        constraint["name"] for constraint in inspector.get_unique_constraints(table_name)
    }


def _next_sucursal_codigo(bind: sa.Connection, sucursal: sa.Table, empresa_id: object) -> str:
    existing_codes = {
        code
        for code in bind.execute(
            sa.select(sucursal.c.codigo).where(sucursal.c.empresa_id == empresa_id)
        ).scalars()
        if code is not None
    }
    for value in range(2, 1000):
        code = f"{value:03d}"
        if code not in existing_codes:
            return code
    raise ValueError(f"No hay codigo de sucursal disponible para empresa {empresa_id}")


def upgrade() -> None:
    bind = op.get_bind()

    empresa_columns = _table_columns("tbl_empresa")
    if "codigo_establecimiento" in empresa_columns:
        op.drop_column("tbl_empresa", "codigo_establecimiento")

    sucursal_columns = _table_columns("tbl_sucursal")
    if "es_matriz" not in sucursal_columns:
        op.add_column(
            "tbl_sucursal",
            sa.Column("es_matriz", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        )

    op.execute(
        sa.text(
            "UPDATE tbl_sucursal "
            "SET es_matriz = CASE WHEN codigo = '001' THEN true ELSE COALESCE(es_matriz, false) END"
        )
    )
    op.alter_column("tbl_sucursal", "es_matriz", existing_type=sa.Boolean(), nullable=False)
    op.alter_column("tbl_sucursal", "es_matriz", existing_type=sa.Boolean(), server_default=None)

    punto_columns = _table_columns("tbl_punto_emision")
    if "empresa_id" in punto_columns and "sucursal_id" in punto_columns:
        punto_emision = _table_clause("tbl_punto_emision")
        sucursal = _table_clause("tbl_sucursal")
        _drop_unique_if_exists("tbl_punto_emision", "uq_pe_empresa_sucursal_codigo")

        rows_without_sucursal = bind.execute(
            sa.select(punto_emision.c.id, punto_emision.c.empresa_id, punto_emision.c.codigo).where(
                punto_emision.c.sucursal_id.is_(None)
            )
        ).all()

        for row in rows_without_sucursal:
            matriz_id = bind.execute(
                sa.select(sucursal.c.id)
                .where(
                    sa.and_(
                        sucursal.c.empresa_id == row.empresa_id,
                        sucursal.c.codigo == "001",
                    )
                )
                .limit(1)
            ).scalar_one_or_none()

            if matriz_id is None:
                now = datetime.utcnow()
                matriz_id = uuid4()
                values: dict[str, object] = {
                    "id": matriz_id,
                    "codigo": "001",
                    "nombre": "Matriz",
                    "direccion": "Matriz",
                    "empresa_id": row.empresa_id,
                }
                if "telefono" in sucursal.c:
                    values["telefono"] = None
                if "es_matriz" in sucursal.c:
                    values["es_matriz"] = True
                if "activo" in sucursal.c:
                    values["activo"] = True
                if "creado_en" in sucursal.c:
                    values["creado_en"] = now
                if "actualizado_en" in sucursal.c:
                    values["actualizado_en"] = now
                if "usuario_auditoria" in sucursal.c:
                    values["usuario_auditoria"] = "alembic_migration"
                if "created_by" in sucursal.c:
                    values["created_by"] = "alembic_migration"
                if "updated_by" in sucursal.c:
                    values["updated_by"] = "alembic_migration"

                bind.execute(sa.insert(sucursal).values(values))
            else:
                if "es_matriz" in sucursal.c:
                    bind.execute(
                        sa.update(sucursal).where(sucursal.c.id == matriz_id).values(es_matriz=True)
                    )

            target_sucursal_id = matriz_id
            already_exists = bind.execute(
                sa.select(sa.literal(1))
                .select_from(punto_emision)
                .where(
                    sa.and_(
                        punto_emision.c.sucursal_id == matriz_id,
                        punto_emision.c.codigo == row.codigo,
                        punto_emision.c.id != row.id,
                    )
                )
                .limit(1)
            ).first()

            if already_exists is not None:
                now = datetime.utcnow()
                target_sucursal_id = uuid4()
                fallback_codigo = _next_sucursal_codigo(bind, sucursal, row.empresa_id)
                values: dict[str, object] = {
                    "id": target_sucursal_id,
                    "codigo": fallback_codigo,
                    "nombre": f"Sucursal migracion {fallback_codigo}",
                    "direccion": "Direccion pendiente de regularizacion",
                    "empresa_id": row.empresa_id,
                }
                if "telefono" in sucursal.c:
                    values["telefono"] = None
                if "es_matriz" in sucursal.c:
                    values["es_matriz"] = False
                if "activo" in sucursal.c:
                    values["activo"] = True
                if "creado_en" in sucursal.c:
                    values["creado_en"] = now
                if "actualizado_en" in sucursal.c:
                    values["actualizado_en"] = now
                if "usuario_auditoria" in sucursal.c:
                    values["usuario_auditoria"] = "alembic_migration"
                if "created_by" in sucursal.c:
                    values["created_by"] = "alembic_migration"
                if "updated_by" in sucursal.c:
                    values["updated_by"] = "alembic_migration"
                bind.execute(sa.insert(sucursal).values(values))

            bind.execute(
                sa.update(punto_emision)
                .where(punto_emision.c.id == row.id)
                .values(sucursal_id=target_sucursal_id)
            )

        _drop_fk_for_column("tbl_punto_emision", "empresa_id")

        op.alter_column("tbl_punto_emision", "sucursal_id", existing_type=sa.Uuid(), nullable=False)

        op.drop_column("tbl_punto_emision", "empresa_id")

    if not _unique_exists("tbl_punto_emision", "uq_pe_sucursal_codigo"):
        op.create_unique_constraint(
            "uq_pe_sucursal_codigo",
            "tbl_punto_emision",
            ["sucursal_id", "codigo"],
        )


def downgrade() -> None:
    bind = op.get_bind()

    empresa_columns = _table_columns("tbl_empresa")
    if "codigo_establecimiento" not in empresa_columns:
        op.add_column(
            "tbl_empresa",
            sa.Column("codigo_establecimiento", sa.String(length=3), nullable=True),
        )

    punto_columns = _table_columns("tbl_punto_emision")
    if "empresa_id" not in punto_columns:
        op.add_column("tbl_punto_emision", sa.Column("empresa_id", sa.Uuid(), nullable=True))

    punto_emision = _table_clause("tbl_punto_emision")
    sucursal = _table_clause("tbl_sucursal")

    if "empresa_id" in punto_emision.c and "sucursal_id" in punto_emision.c:
        empresa_subquery = (
            sa.select(sucursal.c.empresa_id)
            .where(sucursal.c.id == punto_emision.c.sucursal_id)
            .scalar_subquery()
        )
        bind.execute(
            sa.update(punto_emision)
            .where(punto_emision.c.sucursal_id.is_not(None))
            .values(empresa_id=empresa_subquery)
        )
        op.alter_column("tbl_punto_emision", "empresa_id", existing_type=sa.Uuid(), nullable=False)

    _drop_unique_if_exists("tbl_punto_emision", "uq_pe_sucursal_codigo")
    if not _unique_exists("tbl_punto_emision", "uq_pe_empresa_sucursal_codigo"):
        op.create_unique_constraint(
            "uq_pe_empresa_sucursal_codigo",
            "tbl_punto_emision",
            ["empresa_id", "sucursal_id", "codigo"],
        )

    inspector = sa.inspect(op.get_bind())
    has_empresa_fk = any(
        "empresa_id" in fk.get("constrained_columns", [])
        for fk in inspector.get_foreign_keys("tbl_punto_emision")
    )
    if not has_empresa_fk:
        op.create_foreign_key(
            "fk_tbl_punto_emision_empresa_id_tbl_empresa",
            "tbl_punto_emision",
            "tbl_empresa",
            ["empresa_id"],
            ["id"],
        )

    op.alter_column("tbl_punto_emision", "sucursal_id", existing_type=sa.Uuid(), nullable=True)

    sucursal_columns = _table_columns("tbl_sucursal")
    if "es_matriz" in sucursal_columns:
        op.drop_column("tbl_sucursal", "es_matriz")
