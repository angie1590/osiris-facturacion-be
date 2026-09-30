"""add company artisan, tax and signature configuration

Revision ID: a8c2e4f6b9d1
Revises: 9f4b2c1d7e8a
"""

from alembic import op
import sqlalchemy as sa


revision = "a8c2e4f6b9d1"
down_revision = "9f4b2c1d7e8a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tbl_empresa",
        sa.Column("artesano_calificado", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "tbl_empresa",
        sa.Column("impuesto_catalogo_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column("tbl_empresa", sa.Column("firma_electronica_cifrada", sa.LargeBinary(), nullable=True))
    op.add_column("tbl_empresa", sa.Column("firma_password_cifrada", sa.LargeBinary(), nullable=True))
    op.add_column("tbl_empresa", sa.Column("firma_nombre_archivo", sa.String(length=255), nullable=True))
    op.add_column("tbl_empresa", sa.Column("firma_caduca_en", sa.DateTime(), nullable=True))
    op.execute(
        "UPDATE tbl_empresa SET modo_emision = 'NOTA_VENTA_FISICA' "
        "WHERE regimen = 'RIMPE_NEGOCIO_POPULAR'"
    )
    op.drop_constraint("ck_tbl_empresa_regimen_modo_emision", "tbl_empresa", type_="check")
    op.create_check_constraint(
        "ck_tbl_empresa_regimen_modo_emision",
        "tbl_empresa",
        "(modo_emision = 'NOTA_VENTA_FISICA' AND (regimen = 'RIMPE_NEGOCIO_POPULAR' OR artesano_calificado = true)) OR (modo_emision = 'ELECTRONICO' AND regimen <> 'RIMPE_NEGOCIO_POPULAR' AND artesano_calificado = false)",
    )
    op.alter_column("tbl_empresa", "artesano_calificado", server_default=None)
    op.alter_column("tbl_empresa", "impuesto_catalogo_ids", server_default=None)


def downgrade() -> None:
    op.execute(
        "UPDATE tbl_empresa SET modo_emision = 'ELECTRONICO' "
        "WHERE artesano_calificado = true AND regimen <> 'RIMPE_NEGOCIO_POPULAR'"
    )
    op.drop_constraint("ck_tbl_empresa_regimen_modo_emision", "tbl_empresa", type_="check")
    op.create_check_constraint(
        "ck_tbl_empresa_regimen_modo_emision",
        "tbl_empresa",
        "NOT (modo_emision = 'NOTA_VENTA_FISICA' AND regimen <> 'RIMPE_NEGOCIO_POPULAR')",
    )
    for column in (
        "firma_caduca_en",
        "firma_nombre_archivo",
        "firma_password_cifrada",
        "firma_electronica_cifrada",
        "impuesto_catalogo_ids",
        "artesano_calificado",
    ):
        op.drop_column("tbl_empresa", column)