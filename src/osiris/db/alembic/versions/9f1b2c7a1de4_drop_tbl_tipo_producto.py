"""
Drop tbl_tipo_producto table (producto-atributo mapping deprecated).

Revision ID: 9f1b2c7a1de4
Revises: 4d0f0ae69511
Create Date: 2025-12-02 12:25:00
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "9f1b2c7a1de4"
down_revision = "4d0f0ae69511"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.drop_table("tbl_tipo_producto")


def downgrade() -> None:
    op.create_table(
        "tbl_tipo_producto",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("creado_en", sa.DateTime(), nullable=True),
        sa.Column("actualizado_en", sa.DateTime(), nullable=True),
        sa.Column("usuario_auditoria", sa.String(length=255), nullable=True),
        sa.Column("producto_id", sa.UUID(), nullable=False),
        sa.Column("atributo_id", sa.UUID(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=True),
        sa.Column("obligatorio", sa.Boolean(), nullable=True),
        sa.Column("valor", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tbl_tipo_producto_producto_id", "tbl_tipo_producto", ["producto_id"], unique=False)
    op.create_index("ix_tbl_tipo_producto_atributo_id", "tbl_tipo_producto", ["atributo_id"], unique=False)
