"""add producto atributo valor typed eav

Revision ID: 2485b897f986
Revises: b2e4f6a8c0d2
Create Date: 2026-02-22 21:29:28.985350

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '2485b897f986'
down_revision: Union[str, None] = 'b2e4f6a8c0d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tbl_producto_atributo_valor",
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False),
        sa.Column("created_by", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column("updated_by", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column("usuario_auditoria", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("producto_id", sa.Uuid(), nullable=False),
        sa.Column("atributo_id", sa.Uuid(), nullable=False),
        sa.Column("valor_string", sa.String(), nullable=True),
        sa.Column("valor_integer", sa.Integer(), nullable=True),
        sa.Column("valor_decimal", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("valor_boolean", sa.Boolean(), nullable=True),
        sa.Column("valor_date", sa.Date(), nullable=True),
        sa.CheckConstraint(
            """
            (
                CASE WHEN valor_string IS NOT NULL THEN 1 ELSE 0 END +
                CASE WHEN valor_integer IS NOT NULL THEN 1 ELSE 0 END +
                CASE WHEN valor_decimal IS NOT NULL THEN 1 ELSE 0 END +
                CASE WHEN valor_boolean IS NOT NULL THEN 1 ELSE 0 END +
                CASE WHEN valor_date IS NOT NULL THEN 1 ELSE 0 END
            ) = 1
            """,
            name="ck_producto_atributo_valor_one_nonnull",
        ),
        sa.ForeignKeyConstraint(["producto_id"], ["tbl_producto.id"]),
        sa.ForeignKeyConstraint(["atributo_id"], ["tbl_atributo.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("producto_id", "atributo_id", name="uq_producto_atributo"),
    )
    op.create_index(
        op.f("ix_tbl_producto_atributo_valor_activo"),
        "tbl_producto_atributo_valor",
        ["activo"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_producto_atributo_valor_atributo_id"),
        "tbl_producto_atributo_valor",
        ["atributo_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_producto_atributo_valor_created_by"),
        "tbl_producto_atributo_valor",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_producto_atributo_valor_id"),
        "tbl_producto_atributo_valor",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_producto_atributo_valor_producto_id"),
        "tbl_producto_atributo_valor",
        ["producto_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_producto_atributo_valor_updated_by"),
        "tbl_producto_atributo_valor",
        ["updated_by"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_tbl_producto_atributo_valor_updated_by"),
        table_name="tbl_producto_atributo_valor",
    )
    op.drop_index(
        op.f("ix_tbl_producto_atributo_valor_producto_id"),
        table_name="tbl_producto_atributo_valor",
    )
    op.drop_index(
        op.f("ix_tbl_producto_atributo_valor_id"),
        table_name="tbl_producto_atributo_valor",
    )
    op.drop_index(
        op.f("ix_tbl_producto_atributo_valor_created_by"),
        table_name="tbl_producto_atributo_valor",
    )
    op.drop_index(
        op.f("ix_tbl_producto_atributo_valor_atributo_id"),
        table_name="tbl_producto_atributo_valor",
    )
    op.drop_index(
        op.f("ix_tbl_producto_atributo_valor_activo"),
        table_name="tbl_producto_atributo_valor",
    )
    op.drop_table("tbl_producto_atributo_valor")
