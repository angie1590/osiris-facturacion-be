"""add state history tables for facturacion workflow

Revision ID: 8e2f4c1d9a77
Revises: 3c8d2e7a4b11
Create Date: 2026-02-19 13:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8e2f4c1d9a77"
down_revision = "3c8d2e7a4b11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tbl_venta",
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="EMITIDA"),
    )
    op.add_column(
        "tbl_compra",
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="PENDIENTE"),
    )
    op.create_index(op.f("ix_tbl_venta_estado"), "tbl_venta", ["estado"], unique=False)
    op.create_index(op.f("ix_tbl_compra_estado"), "tbl_compra", ["estado"], unique=False)
    op.create_check_constraint(
        "ck_tbl_venta_estado",
        "tbl_venta",
        "estado IN ('PENDIENTE', 'EMITIDA', 'ANULADA')",
    )
    op.create_check_constraint(
        "ck_tbl_compra_estado",
        "tbl_compra",
        "estado IN ('PENDIENTE', 'PAGADA', 'ANULADA')",
    )

    op.create_table(
        "tbl_documento_electronico",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("venta_id", sa.Uuid(), nullable=False),
        sa.Column("clave_acceso", sa.String(length=49), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="ENVIADO"),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("usuario_auditoria", sa.String(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["venta_id"], ["tbl_venta.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tbl_documento_electronico_id"), "tbl_documento_electronico", ["id"], unique=False)
    op.create_index(
        op.f("ix_tbl_documento_electronico_venta_id"),
        "tbl_documento_electronico",
        ["venta_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_documento_electronico_clave_acceso"),
        "tbl_documento_electronico",
        ["clave_acceso"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_documento_electronico_activo"),
        "tbl_documento_electronico",
        ["activo"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_documento_electronico_created_by"),
        "tbl_documento_electronico",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_documento_electronico_updated_by"),
        "tbl_documento_electronico",
        ["updated_by"],
        unique=False,
    )
    op.create_check_constraint(
        "ck_tbl_documento_electronico_estado",
        "tbl_documento_electronico",
        "estado IN ('ENVIADO', 'AUTORIZADO', 'RECHAZADO')",
    )

    op.create_table(
        "tbl_venta_estado_historial",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entidad_id", sa.Uuid(), nullable=False),
        sa.Column("estado_anterior", sa.String(length=30), nullable=False),
        sa.Column("estado_nuevo", sa.String(length=30), nullable=False),
        sa.Column("motivo_cambio", sa.Text(), nullable=False),
        sa.Column("usuario_id", sa.String(length=255), nullable=True),
        sa.Column("fecha", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["entidad_id"], ["tbl_venta.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tbl_venta_estado_historial_id"),
        "tbl_venta_estado_historial",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_venta_estado_historial_entidad_id"),
        "tbl_venta_estado_historial",
        ["entidad_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_venta_estado_historial_usuario_id"),
        "tbl_venta_estado_historial",
        ["usuario_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_venta_estado_historial_fecha"),
        "tbl_venta_estado_historial",
        ["fecha"],
        unique=False,
    )

    op.create_table(
        "tbl_compra_estado_historial",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entidad_id", sa.Uuid(), nullable=False),
        sa.Column("estado_anterior", sa.String(length=30), nullable=False),
        sa.Column("estado_nuevo", sa.String(length=30), nullable=False),
        sa.Column("motivo_cambio", sa.Text(), nullable=False),
        sa.Column("usuario_id", sa.String(length=255), nullable=True),
        sa.Column("fecha", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["entidad_id"], ["tbl_compra.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tbl_compra_estado_historial_id"),
        "tbl_compra_estado_historial",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_compra_estado_historial_entidad_id"),
        "tbl_compra_estado_historial",
        ["entidad_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_compra_estado_historial_usuario_id"),
        "tbl_compra_estado_historial",
        ["usuario_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_compra_estado_historial_fecha"),
        "tbl_compra_estado_historial",
        ["fecha"],
        unique=False,
    )

    op.create_table(
        "tbl_documento_electronico_historial",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entidad_id", sa.Uuid(), nullable=False),
        sa.Column("estado_anterior", sa.String(length=30), nullable=False),
        sa.Column("estado_nuevo", sa.String(length=30), nullable=False),
        sa.Column("motivo_cambio", sa.Text(), nullable=False),
        sa.Column("usuario_id", sa.String(length=255), nullable=True),
        sa.Column("fecha", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["entidad_id"], ["tbl_documento_electronico.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tbl_documento_electronico_historial_id"),
        "tbl_documento_electronico_historial",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_documento_electronico_historial_entidad_id"),
        "tbl_documento_electronico_historial",
        ["entidad_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_documento_electronico_historial_usuario_id"),
        "tbl_documento_electronico_historial",
        ["usuario_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_documento_electronico_historial_fecha"),
        "tbl_documento_electronico_historial",
        ["fecha"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_tbl_documento_electronico_historial_fecha"), table_name="tbl_documento_electronico_historial")
    op.drop_index(op.f("ix_tbl_documento_electronico_historial_usuario_id"), table_name="tbl_documento_electronico_historial")
    op.drop_index(op.f("ix_tbl_documento_electronico_historial_entidad_id"), table_name="tbl_documento_electronico_historial")
    op.drop_index(op.f("ix_tbl_documento_electronico_historial_id"), table_name="tbl_documento_electronico_historial")
    op.drop_table("tbl_documento_electronico_historial")

    op.drop_index(op.f("ix_tbl_compra_estado_historial_fecha"), table_name="tbl_compra_estado_historial")
    op.drop_index(op.f("ix_tbl_compra_estado_historial_usuario_id"), table_name="tbl_compra_estado_historial")
    op.drop_index(op.f("ix_tbl_compra_estado_historial_entidad_id"), table_name="tbl_compra_estado_historial")
    op.drop_index(op.f("ix_tbl_compra_estado_historial_id"), table_name="tbl_compra_estado_historial")
    op.drop_table("tbl_compra_estado_historial")

    op.drop_index(op.f("ix_tbl_venta_estado_historial_fecha"), table_name="tbl_venta_estado_historial")
    op.drop_index(op.f("ix_tbl_venta_estado_historial_usuario_id"), table_name="tbl_venta_estado_historial")
    op.drop_index(op.f("ix_tbl_venta_estado_historial_entidad_id"), table_name="tbl_venta_estado_historial")
    op.drop_index(op.f("ix_tbl_venta_estado_historial_id"), table_name="tbl_venta_estado_historial")
    op.drop_table("tbl_venta_estado_historial")

    op.drop_constraint("ck_tbl_documento_electronico_estado", "tbl_documento_electronico", type_="check")
    op.drop_index(op.f("ix_tbl_documento_electronico_updated_by"), table_name="tbl_documento_electronico")
    op.drop_index(op.f("ix_tbl_documento_electronico_created_by"), table_name="tbl_documento_electronico")
    op.drop_index(op.f("ix_tbl_documento_electronico_activo"), table_name="tbl_documento_electronico")
    op.drop_index(op.f("ix_tbl_documento_electronico_clave_acceso"), table_name="tbl_documento_electronico")
    op.drop_index(op.f("ix_tbl_documento_electronico_venta_id"), table_name="tbl_documento_electronico")
    op.drop_index(op.f("ix_tbl_documento_electronico_id"), table_name="tbl_documento_electronico")
    op.drop_table("tbl_documento_electronico")

    op.drop_constraint("ck_tbl_compra_estado", "tbl_compra", type_="check")
    op.drop_constraint("ck_tbl_venta_estado", "tbl_venta", type_="check")
    op.drop_index(op.f("ix_tbl_compra_estado"), table_name="tbl_compra")
    op.drop_index(op.f("ix_tbl_venta_estado"), table_name="tbl_venta")
    op.drop_column("tbl_compra", "estado")
    op.drop_column("tbl_venta", "estado")
