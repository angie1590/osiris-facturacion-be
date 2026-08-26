"""enforce empresa regimen/modo and add before_json after_json

Revision ID: e4f6a8b0c2d1
Revises: c2d4e6f8a1b3
Create Date: 2026-02-19 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e4f6a8b0c2d1"
down_revision: Union[str, None] = "c2d4e6f8a1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("audit_log", sa.Column("before_json", sa.JSON(), nullable=True))
    op.add_column("audit_log", sa.Column("after_json", sa.JSON(), nullable=True))

    op.create_check_constraint(
        "ck_tbl_empresa_regimen_modo_emision",
        "tbl_empresa",
        "NOT (modo_emision = 'NOTA_VENTA_FISICA' AND regimen <> 'RIMPE_NEGOCIO_POPULAR')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_tbl_empresa_regimen_modo_emision", "tbl_empresa", type_="check")
    op.drop_column("audit_log", "after_json")
    op.drop_column("audit_log", "before_json")
