"""Add configurable catalog-backed attribute types and branch mappings.

Revision ID: c5e8b2a64d31
Revises: b84c1d6e2f90
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "c5e8b2a64d31"
down_revision = "b84c1d6e2f90"
branch_labels = None
depends_on = None


def _preflight() -> None:
    bind = op.get_bind()
    mappings = sa.table(
        "tbl_categoria_atributo",
        sa.column("id", sa.Uuid()),
        sa.column("categoria_id", sa.Uuid()),
        sa.column("atributo_id", sa.Uuid()),
        sa.column("activo", sa.Boolean()),
    )
    duplicates = bind.execute(
        sa.select(
            mappings.c.categoria_id,
            mappings.c.atributo_id,
            sa.func.count().label("total"),
        )
        .where(mappings.c.activo.is_(True))
        .group_by(mappings.c.categoria_id, mappings.c.atributo_id)
        .having(sa.func.count() > 1)
        .limit(20)
    ).all()
    if duplicates:
        details = ", ".join(
            f"categoria={row.categoria_id}/atributo={row.atributo_id} ({row.total})"
            for row in duplicates
        )
        raise RuntimeError(
            "Cannot enforce active category/attribute uniqueness; resolve duplicate mappings first: "
            f"{details}"
        )


def upgrade() -> None:
    _preflight()
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute("ALTER TYPE tipodato ADD VALUE IF NOT EXISTS 'SELECT'")
        op.execute("ALTER TYPE tipodato ADD VALUE IF NOT EXISTS 'CATALOG'")

    op.create_table(
        "tbl_catalogo",
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False),
        sa.Column("usuario_auditoria", sa.String(length=255), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("descripcion", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nombre", name="uq_tbl_catalogo_nombre"),
    )
    op.create_index("ix_tbl_catalogo_activo", "tbl_catalogo", ["activo"])
    op.create_index("ix_tbl_catalogo_nombre", "tbl_catalogo", ["nombre"])

    op.create_table(
        "tbl_catalogo_valor",
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False),
        sa.Column("usuario_auditoria", sa.String(length=255), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("catalogo_id", sa.Uuid(), nullable=False),
        sa.Column("valor", sa.String(length=255), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["catalogo_id"], ["tbl_catalogo.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tbl_catalogo_valor_catalogo_id", "tbl_catalogo_valor", ["catalogo_id"])
    op.create_index(
        "uq_tbl_catalogo_valor_activo",
        "tbl_catalogo_valor",
        ["catalogo_id", sa.text("lower(valor)")],
        unique=True,
        postgresql_where=sa.text("activo = true"),
        sqlite_where=sa.text("activo = 1"),
    )

    inspector = sa.inspect(bind)
    attribute_indexes = {index["name"] for index in inspector.get_indexes("tbl_atributo")}
    if "ix_tbl_atributo_nombre" in attribute_indexes:
        op.drop_index("ix_tbl_atributo_nombre", table_name="tbl_atributo")
    with op.batch_alter_table("tbl_atributo") as batch_op:
        batch_op.add_column(sa.Column("select_options", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("catalog_id", sa.Uuid(), nullable=True))
        batch_op.add_column(
            sa.Column("allow_negative", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("min_value", sa.Numeric(18, 6), nullable=True))
        batch_op.add_column(sa.Column("max_value", sa.Numeric(18, 6), nullable=True))
        batch_op.create_foreign_key("fk_tbl_atributo_catalog_id", "tbl_catalogo", ["catalog_id"], ["id"])
    op.create_index("ix_tbl_atributo_catalog_id", "tbl_atributo", ["catalog_id"])

    op.create_index(
        "uq_tbl_categoria_atributo_activo",
        "tbl_categoria_atributo",
        ["categoria_id", "atributo_id"],
        unique=True,
        postgresql_where=sa.text("activo = true"),
        sqlite_where=sa.text("activo = 1"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    used_types = bind.execute(
        sa.text("SELECT id FROM tbl_atributo WHERE tipo_dato IN ('SELECT', 'CATALOG') LIMIT 1")
    ).first()
    if used_types:
        raise RuntimeError("Cannot downgrade while SELECT or CATALOG attributes exist; migrate them first.")

    duplicates = bind.execute(
        sa.text(
            "SELECT lower(nombre) FROM tbl_atributo GROUP BY lower(nombre) HAVING count(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicates:
        raise RuntimeError("Cannot restore global attribute-name uniqueness while duplicate names exist.")

    op.drop_index("uq_tbl_categoria_atributo_activo", table_name="tbl_categoria_atributo")
    op.drop_index("ix_tbl_atributo_catalog_id", table_name="tbl_atributo")
    with op.batch_alter_table("tbl_atributo") as batch_op:
        batch_op.drop_constraint("fk_tbl_atributo_catalog_id", type_="foreignkey")
        batch_op.drop_column("max_value")
        batch_op.drop_column("min_value")
        batch_op.drop_column("allow_negative")
        batch_op.drop_column("catalog_id")
        batch_op.drop_column("select_options")
    op.create_index("ix_tbl_atributo_nombre", "tbl_atributo", ["nombre"], unique=True)

    op.drop_index("uq_tbl_catalogo_valor_activo", table_name="tbl_catalogo_valor")
    op.drop_index("ix_tbl_catalogo_valor_catalogo_id", table_name="tbl_catalogo_valor")
    op.drop_table("tbl_catalogo_valor")
    op.drop_index("ix_tbl_catalogo_nombre", table_name="tbl_catalogo")
    op.drop_index("ix_tbl_catalogo_activo", table_name="tbl_catalogo")
    op.drop_table("tbl_catalogo")

    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE tbl_atributo ALTER COLUMN tipo_dato TYPE VARCHAR(16) USING tipo_dato::text")
        op.execute("DROP TYPE tipodato")
        op.execute("CREATE TYPE tipodato AS ENUM ('STRING', 'INTEGER', 'DECIMAL', 'BOOLEAN', 'DATE')")
        op.execute("ALTER TABLE tbl_atributo ALTER COLUMN tipo_dato TYPE tipodato USING tipo_dato::tipodato")