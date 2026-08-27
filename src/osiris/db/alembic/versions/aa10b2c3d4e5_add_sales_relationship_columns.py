"""add sales relationship columns

Revision ID: aa10b2c3d4e5
Revises: 9f1d3c2a7b44
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "aa10b2c3d4e5"
down_revision: Union[str, None] = "9f1d3c2a7b44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tbl_venta", sa.Column("cliente_id", sa.Uuid(), nullable=True))
    op.add_column("tbl_venta", sa.Column("empresa_id", sa.Uuid(), nullable=True))
    op.add_column("tbl_venta", sa.Column("punto_emision_id", sa.Uuid(), nullable=True))
    op.add_column("tbl_venta", sa.Column("bodega_id", sa.Uuid(), nullable=True))
    op.add_column("tbl_venta", sa.Column("secuencial_formateado", sa.String(length=20), nullable=True))
    op.add_column("tbl_venta", sa.Column("tipo_emision", sa.String(length=25), nullable=False, server_default="ELECTRONICA"))
    op.add_column("tbl_venta", sa.Column("estado_sri", sa.String(length=20), nullable=False, server_default="PENDIENTE"))
    op.add_column("tbl_venta", sa.Column("sri_intentos", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("tbl_venta", sa.Column("sri_ultimo_error", sa.String(length=1000), nullable=True))
    op.add_column("tbl_venta", sa.Column("cantidad_impresiones", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_tbl_venta_cliente_id", "tbl_venta", ["cliente_id"])
    op.create_index("ix_tbl_venta_empresa_id", "tbl_venta", ["empresa_id"])
    op.create_index("ix_tbl_venta_punto_emision_id", "tbl_venta", ["punto_emision_id"])
    op.create_index("ix_tbl_venta_bodega_id", "tbl_venta", ["bodega_id"])
    op.create_index("ix_tbl_venta_secuencial_formateado", "tbl_venta", ["secuencial_formateado"])
    op.create_foreign_key("fk_tbl_venta_cliente_id", "tbl_venta", "tbl_cliente", ["cliente_id"], ["id"])
    op.create_foreign_key("fk_tbl_venta_empresa_id", "tbl_venta", "tbl_empresa", ["empresa_id"], ["id"])
    op.create_foreign_key("fk_tbl_venta_punto_emision_id", "tbl_venta", "tbl_punto_emision", ["punto_emision_id"], ["id"])
    op.create_foreign_key("fk_tbl_venta_bodega_id", "tbl_venta", "tbl_bodega", ["bodega_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_tbl_venta_bodega_id", "tbl_venta", type_="foreignkey")
    op.drop_constraint("fk_tbl_venta_punto_emision_id", "tbl_venta", type_="foreignkey")
    op.drop_constraint("fk_tbl_venta_empresa_id", "tbl_venta", type_="foreignkey")
    op.drop_constraint("fk_tbl_venta_cliente_id", "tbl_venta", type_="foreignkey")
    op.drop_index("ix_tbl_venta_bodega_id", table_name="tbl_venta")
    op.drop_index("ix_tbl_venta_secuencial_formateado", table_name="tbl_venta")
    op.drop_index("ix_tbl_venta_punto_emision_id", table_name="tbl_venta")
    op.drop_index("ix_tbl_venta_empresa_id", table_name="tbl_venta")
    op.drop_index("ix_tbl_venta_cliente_id", table_name="tbl_venta")
    op.drop_column("tbl_venta", "bodega_id")
    op.drop_column("tbl_venta", "cantidad_impresiones")
    op.drop_column("tbl_venta", "sri_ultimo_error")
    op.drop_column("tbl_venta", "sri_intentos")
    op.drop_column("tbl_venta", "estado_sri")
    op.drop_column("tbl_venta", "tipo_emision")
    op.drop_column("tbl_venta", "secuencial_formateado")
    op.drop_column("tbl_venta", "punto_emision_id")
    op.drop_column("tbl_venta", "empresa_id")
    op.drop_column("tbl_venta", "cliente_id")
