"""convert tipo_cliente descuento to numeric(5,2)

Revision ID: b2e4f6a8c0d2
Revises: a1b2c3d4e5f6
Create Date: 2026-02-22 18:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2e4f6a8c0d2"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column(
            "tbl_tipo_cliente",
            "descuento",
            existing_type=sa.Integer(),
            type_=sa.Numeric(5, 2),
            nullable=False,
            postgresql_using="descuento::numeric(5,2)",
        )
    else:
        with op.batch_alter_table("tbl_tipo_cliente") as batch_op:
            batch_op.alter_column(
                "descuento",
                existing_type=sa.Integer(),
                type_=sa.Numeric(5, 2),
                nullable=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column(
            "tbl_tipo_cliente",
            "descuento",
            existing_type=sa.Numeric(5, 2),
            type_=sa.Integer(),
            nullable=False,
            postgresql_using="ROUND(descuento)::integer",
        )
    else:
        with op.batch_alter_table("tbl_tipo_cliente") as batch_op:
            batch_op.alter_column(
                "descuento",
                existing_type=sa.Numeric(5, 2),
                type_=sa.Integer(),
                nullable=False,
            )
