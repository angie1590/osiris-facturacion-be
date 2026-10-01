"""expand audit action length for descriptive events

Revision ID: e3b91a7d5c20
Revises: d7a4c91e2f60
"""

from alembic import op
import sqlalchemy as sa


revision = "e3b91a7d5c20"
down_revision = "d7a4c91e2f60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("audit_log") as batch_op:
        batch_op.alter_column(
            "accion",
            existing_type=sa.String(length=20),
            type_=sa.String(length=64),
            existing_nullable=False,
        )


def downgrade() -> None:
    connection = op.get_bind()
    long_actions = connection.execute(
        sa.text("SELECT count(*) FROM audit_log WHERE length(accion) > 20")
    ).scalar_one()
    if long_actions:
        raise RuntimeError("Cannot downgrade audit_log.accion while actions longer than 20 characters exist.")
    with op.batch_alter_table("audit_log") as batch_op:
        batch_op.alter_column(
            "accion",
            existing_type=sa.String(length=64),
            type_=sa.String(length=20),
            existing_nullable=False,
        )
