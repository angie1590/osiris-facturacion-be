"""add temporary tax measures and sale tax component snapshots

Revision ID: c9d3e6a1b742
Revises: a8c2e4f6b9d1
"""

from alembic import op
import sqlalchemy as sa


revision = "c9d3e6a1b742"
down_revision = "a8c2e4f6b9d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tbl_venta",
        sa.Column("subtotal_8", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
    )
    op.create_table(
        "tbl_medida_tributaria_temporal",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.Column("usuario_auditoria", sa.String(255), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("empresa_id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(180), nullable=False),
        sa.Column("referencia_legal", sa.Text(), nullable=False),
        sa.Column("tipo_impuesto", sa.String(10), nullable=False),
        sa.Column("componente", sa.String(20), nullable=False),
        sa.Column("fecha_inicio", sa.Date(), nullable=False),
        sa.Column("fecha_fin", sa.Date(), nullable=False),
        sa.Column("codigo_impuesto_sri", sa.String(10), nullable=False),
        sa.Column("codigo_porcentaje_sri", sa.String(10), nullable=False),
        sa.Column("codigo_sri_confirmado", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("tarifa", sa.Numeric(12, 6), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False),
        sa.CheckConstraint("fecha_fin >= fecha_inicio", name="ck_medida_temporal_fechas"),
        sa.CheckConstraint("tarifa >= 0", name="ck_medida_temporal_tarifa"),
        sa.ForeignKeyConstraint(["empresa_id"], ["tbl_empresa.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tbl_medida_temporal_empresa", "tbl_medida_tributaria_temporal", ["empresa_id"])
    op.create_index("ix_tbl_medida_temporal_inicio", "tbl_medida_tributaria_temporal", ["fecha_inicio"])
    op.create_index("ix_tbl_medida_temporal_fin", "tbl_medida_tributaria_temporal", ["fecha_fin"])
    op.create_index("ix_tbl_medida_temporal_estado", "tbl_medida_tributaria_temporal", ["estado"])
    op.create_index("ix_tbl_medida_temporal_activo", "tbl_medida_tributaria_temporal", ["activo"])

    op.create_table(
        "tbl_medida_tributaria_producto",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.Column("usuario_auditoria", sa.String(255), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("medida_id", sa.Uuid(), nullable=False),
        sa.Column("producto_id", sa.Uuid(), nullable=False),
        sa.Column("factor_cantidad", sa.Numeric(14, 8), nullable=True),
        sa.Column("unidad_gravable", sa.String(40), nullable=True),
        sa.CheckConstraint("factor_cantidad IS NULL OR factor_cantidad > 0", name="ck_medida_producto_factor"),
        sa.ForeignKeyConstraint(["medida_id"], ["tbl_medida_tributaria_temporal.id"]),
        sa.ForeignKeyConstraint(["producto_id"], ["tbl_producto.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tbl_medida_producto_medida", "tbl_medida_tributaria_producto", ["medida_id"])
    op.create_index("ix_tbl_medida_producto_producto", "tbl_medida_tributaria_producto", ["producto_id"])
    op.create_index("ix_tbl_medida_producto_activo", "tbl_medida_tributaria_producto", ["activo"])

    with op.batch_alter_table("tbl_venta_detalle_impuesto") as batch_op:
        batch_op.add_column(
            sa.Column("componente", sa.String(20), nullable=False, server_default="PORCENTUAL")
        )
        batch_op.add_column(sa.Column("unidad_gravable", sa.String(40), nullable=True))
        batch_op.add_column(sa.Column("cantidad_gravable", sa.Numeric(14, 4), nullable=True))
        batch_op.add_column(sa.Column("medida_temporal_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("referencia_legal_temporal", sa.Text(), nullable=True))
        batch_op.create_foreign_key(
            "fk_venta_detalle_impuesto_medida_temporal",
            "tbl_medida_tributaria_temporal",
            ["medida_temporal_id"],
            ["id"],
        )
        batch_op.alter_column(
            "tarifa",
            existing_type=sa.Numeric(7, 4),
            type_=sa.Numeric(12, 6),
            existing_nullable=False,
        )
    op.execute(
        "UPDATE tbl_venta_detalle_impuesto SET componente = 'AD_VALOREM' "
        "WHERE tipo_impuesto = 'ICE'"
    )
    op.create_index(
        "ix_venta_detalle_impuesto_medida_temporal",
        "tbl_venta_detalle_impuesto",
        ["medida_temporal_id"],
    )


def downgrade() -> None:
    op.drop_column("tbl_venta", "subtotal_8")
    op.drop_index("ix_venta_detalle_impuesto_medida_temporal", table_name="tbl_venta_detalle_impuesto")
    with op.batch_alter_table("tbl_venta_detalle_impuesto") as batch_op:
        batch_op.drop_constraint("fk_venta_detalle_impuesto_medida_temporal", type_="foreignkey")
        batch_op.alter_column(
            "tarifa",
            existing_type=sa.Numeric(12, 6),
            type_=sa.Numeric(7, 4),
            existing_nullable=False,
        )
        for column in (
            "referencia_legal_temporal",
            "medida_temporal_id",
            "cantidad_gravable",
            "unidad_gravable",
            "componente",
        ):
            batch_op.drop_column(column)

    op.drop_index("ix_tbl_medida_producto_activo", table_name="tbl_medida_tributaria_producto")
    op.drop_index("ix_tbl_medida_producto_producto", table_name="tbl_medida_tributaria_producto")
    op.drop_index("ix_tbl_medida_producto_medida", table_name="tbl_medida_tributaria_producto")
    op.drop_table("tbl_medida_tributaria_producto")
    op.drop_index("ix_tbl_medida_temporal_activo", table_name="tbl_medida_tributaria_temporal")
    op.drop_index("ix_tbl_medida_temporal_estado", table_name="tbl_medida_tributaria_temporal")
    op.drop_index("ix_tbl_medida_temporal_fin", table_name="tbl_medida_tributaria_temporal")
    op.drop_index("ix_tbl_medida_temporal_inicio", table_name="tbl_medida_tributaria_temporal")
    op.drop_index("ix_tbl_medida_temporal_empresa", table_name="tbl_medida_tributaria_temporal")
    op.drop_table("tbl_medida_tributaria_temporal")
