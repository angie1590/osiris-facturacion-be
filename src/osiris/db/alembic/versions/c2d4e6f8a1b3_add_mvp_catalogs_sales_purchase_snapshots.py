"""add mvp catalogs sales purchase snapshots

Revision ID: c2d4e6f8a1b3
Revises: f9a7b21c3d4e
Create Date: 2026-02-19 14:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c2d4e6f8a1b3"
down_revision: Union[str, None] = "f9a7b21c3d4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tbl_producto_impuesto",
        sa.Column("codigo_impuesto_sri", sa.String(length=10), nullable=False, server_default="2"),
    )
    op.add_column(
        "tbl_producto_impuesto",
        sa.Column("codigo_porcentaje_sri", sa.String(length=10), nullable=False, server_default="0"),
    )
    op.add_column(
        "tbl_producto_impuesto",
        sa.Column("tarifa", sa.Numeric(7, 4), nullable=False, server_default=sa.text("0")),
    )

    op.execute(
        """
        UPDATE tbl_producto_impuesto p
        SET codigo_impuesto_sri = c.codigo_tipo_impuesto,
            codigo_porcentaje_sri = c.codigo_sri,
            tarifa = COALESCE(c.porcentaje_iva, c.tarifa_ad_valorem, 0)
        FROM aux_impuesto_catalogo c
        WHERE p.impuesto_catalogo_id = c.id
        """
    )

    op.create_table(
        "tbl_venta",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("usuario_auditoria", sa.String(length=255), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("fecha_emision", sa.Date(), nullable=False),
        sa.Column("tipo_identificacion_comprador", sa.String(length=20), nullable=False),
        sa.Column("identificacion_comprador", sa.String(length=20), nullable=False),
        sa.Column("forma_pago", sa.String(length=20), nullable=False),
        sa.Column("subtotal_sin_impuestos", sa.Numeric(12, 2), nullable=False),
        sa.Column("subtotal_12", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("subtotal_15", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("subtotal_0", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("subtotal_no_objeto", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("monto_iva", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("monto_ice", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("valor_total", sa.Numeric(12, 2), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tbl_venta_id"), "tbl_venta", ["id"], unique=False)
    op.create_index(
        op.f("ix_tbl_venta_identificacion_comprador"),
        "tbl_venta",
        ["identificacion_comprador"],
        unique=False,
    )
    op.create_index(op.f("ix_tbl_venta_activo"), "tbl_venta", ["activo"], unique=False)

    op.create_table(
        "tbl_venta_detalle",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("usuario_auditoria", sa.String(length=255), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("venta_id", sa.Uuid(), nullable=False),
        sa.Column("producto_id", sa.Uuid(), nullable=False),
        sa.Column("descripcion", sa.String(length=255), nullable=False),
        sa.Column("cantidad", sa.Numeric(12, 4), nullable=False),
        sa.Column("precio_unitario", sa.Numeric(12, 4), nullable=False),
        sa.Column("descuento", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("subtotal_sin_impuesto", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["venta_id"], ["tbl_venta.id"]),
        sa.ForeignKeyConstraint(["producto_id"], ["tbl_producto.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tbl_venta_detalle_id"), "tbl_venta_detalle", ["id"], unique=False)
    op.create_index(op.f("ix_tbl_venta_detalle_venta_id"), "tbl_venta_detalle", ["venta_id"], unique=False)
    op.create_index(op.f("ix_tbl_venta_detalle_producto_id"), "tbl_venta_detalle", ["producto_id"], unique=False)
    op.create_index(op.f("ix_tbl_venta_detalle_activo"), "tbl_venta_detalle", ["activo"], unique=False)

    op.create_table(
        "tbl_venta_detalle_impuesto",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("usuario_auditoria", sa.String(length=255), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("venta_detalle_id", sa.Uuid(), nullable=False),
        sa.Column("tipo_impuesto", sa.String(length=10), nullable=False),
        sa.Column("codigo_impuesto_sri", sa.String(length=10), nullable=False),
        sa.Column("codigo_porcentaje_sri", sa.String(length=10), nullable=False),
        sa.Column("tarifa", sa.Numeric(7, 4), nullable=False),
        sa.Column("base_imponible", sa.Numeric(12, 2), nullable=False),
        sa.Column("valor_impuesto", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["venta_detalle_id"], ["tbl_venta_detalle.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tbl_venta_detalle_impuesto_id"),
        "tbl_venta_detalle_impuesto",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_venta_detalle_impuesto_venta_detalle_id"),
        "tbl_venta_detalle_impuesto",
        ["venta_detalle_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_venta_detalle_impuesto_activo"),
        "tbl_venta_detalle_impuesto",
        ["activo"],
        unique=False,
    )

    op.create_table(
        "tbl_compra",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("usuario_auditoria", sa.String(length=255), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("fecha_emision", sa.Date(), nullable=False),
        sa.Column("tipo_identificacion_proveedor", sa.String(length=20), nullable=False),
        sa.Column("identificacion_proveedor", sa.String(length=20), nullable=False),
        sa.Column("forma_pago", sa.String(length=20), nullable=False),
        sa.Column("subtotal_sin_impuestos", sa.Numeric(12, 2), nullable=False),
        sa.Column("subtotal_12", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("subtotal_15", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("subtotal_0", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("subtotal_no_objeto", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("monto_iva", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("monto_ice", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("valor_total", sa.Numeric(12, 2), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tbl_compra_id"), "tbl_compra", ["id"], unique=False)
    op.create_index(
        op.f("ix_tbl_compra_identificacion_proveedor"),
        "tbl_compra",
        ["identificacion_proveedor"],
        unique=False,
    )
    op.create_index(op.f("ix_tbl_compra_activo"), "tbl_compra", ["activo"], unique=False)

    op.create_table(
        "tbl_compra_detalle",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("usuario_auditoria", sa.String(length=255), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("compra_id", sa.Uuid(), nullable=False),
        sa.Column("producto_id", sa.Uuid(), nullable=False),
        sa.Column("descripcion", sa.String(length=255), nullable=False),
        sa.Column("cantidad", sa.Numeric(12, 4), nullable=False),
        sa.Column("precio_unitario", sa.Numeric(12, 4), nullable=False),
        sa.Column("descuento", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("subtotal_sin_impuesto", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["compra_id"], ["tbl_compra.id"]),
        sa.ForeignKeyConstraint(["producto_id"], ["tbl_producto.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tbl_compra_detalle_id"), "tbl_compra_detalle", ["id"], unique=False)
    op.create_index(op.f("ix_tbl_compra_detalle_compra_id"), "tbl_compra_detalle", ["compra_id"], unique=False)
    op.create_index(op.f("ix_tbl_compra_detalle_producto_id"), "tbl_compra_detalle", ["producto_id"], unique=False)
    op.create_index(op.f("ix_tbl_compra_detalle_activo"), "tbl_compra_detalle", ["activo"], unique=False)

    op.create_table(
        "tbl_compra_detalle_impuesto",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("usuario_auditoria", sa.String(length=255), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("compra_detalle_id", sa.Uuid(), nullable=False),
        sa.Column("tipo_impuesto", sa.String(length=10), nullable=False),
        sa.Column("codigo_impuesto_sri", sa.String(length=10), nullable=False),
        sa.Column("codigo_porcentaje_sri", sa.String(length=10), nullable=False),
        sa.Column("tarifa", sa.Numeric(7, 4), nullable=False),
        sa.Column("base_imponible", sa.Numeric(12, 2), nullable=False),
        sa.Column("valor_impuesto", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["compra_detalle_id"], ["tbl_compra_detalle.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tbl_compra_detalle_impuesto_id"),
        "tbl_compra_detalle_impuesto",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_compra_detalle_impuesto_compra_detalle_id"),
        "tbl_compra_detalle_impuesto",
        ["compra_detalle_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_compra_detalle_impuesto_activo"),
        "tbl_compra_detalle_impuesto",
        ["activo"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_tbl_compra_detalle_impuesto_activo"), table_name="tbl_compra_detalle_impuesto")
    op.drop_index(op.f("ix_tbl_compra_detalle_impuesto_compra_detalle_id"), table_name="tbl_compra_detalle_impuesto")
    op.drop_index(op.f("ix_tbl_compra_detalle_impuesto_id"), table_name="tbl_compra_detalle_impuesto")
    op.drop_table("tbl_compra_detalle_impuesto")

    op.drop_index(op.f("ix_tbl_compra_detalle_activo"), table_name="tbl_compra_detalle")
    op.drop_index(op.f("ix_tbl_compra_detalle_producto_id"), table_name="tbl_compra_detalle")
    op.drop_index(op.f("ix_tbl_compra_detalle_compra_id"), table_name="tbl_compra_detalle")
    op.drop_index(op.f("ix_tbl_compra_detalle_id"), table_name="tbl_compra_detalle")
    op.drop_table("tbl_compra_detalle")

    op.drop_index(op.f("ix_tbl_compra_activo"), table_name="tbl_compra")
    op.drop_index(op.f("ix_tbl_compra_identificacion_proveedor"), table_name="tbl_compra")
    op.drop_index(op.f("ix_tbl_compra_id"), table_name="tbl_compra")
    op.drop_table("tbl_compra")

    op.drop_index(op.f("ix_tbl_venta_detalle_impuesto_activo"), table_name="tbl_venta_detalle_impuesto")
    op.drop_index(op.f("ix_tbl_venta_detalle_impuesto_venta_detalle_id"), table_name="tbl_venta_detalle_impuesto")
    op.drop_index(op.f("ix_tbl_venta_detalle_impuesto_id"), table_name="tbl_venta_detalle_impuesto")
    op.drop_table("tbl_venta_detalle_impuesto")

    op.drop_index(op.f("ix_tbl_venta_detalle_activo"), table_name="tbl_venta_detalle")
    op.drop_index(op.f("ix_tbl_venta_detalle_producto_id"), table_name="tbl_venta_detalle")
    op.drop_index(op.f("ix_tbl_venta_detalle_venta_id"), table_name="tbl_venta_detalle")
    op.drop_index(op.f("ix_tbl_venta_detalle_id"), table_name="tbl_venta_detalle")
    op.drop_table("tbl_venta_detalle")

    op.drop_index(op.f("ix_tbl_venta_activo"), table_name="tbl_venta")
    op.drop_index(op.f("ix_tbl_venta_identificacion_comprador"), table_name="tbl_venta")
    op.drop_index(op.f("ix_tbl_venta_id"), table_name="tbl_venta")
    op.drop_table("tbl_venta")

    op.drop_column("tbl_producto_impuesto", "tarifa")
    op.drop_column("tbl_producto_impuesto", "codigo_porcentaje_sri")
    op.drop_column("tbl_producto_impuesto", "codigo_impuesto_sri")
