"""align electronic document table with current FE model

Revision ID: d7a4c91e2f60
Revises: c9d3e6a1b742
"""

from alembic import op
import sqlalchemy as sa


revision = "d7a4c91e2f60"
down_revision = "c9d3e6a1b742"
branch_labels = None
depends_on = None


CURRENT_DOCUMENT_STATES = "'EN_COLA', 'FIRMADO', 'RECIBIDO', 'ENVIADO', 'AUTORIZADO', 'RECHAZADO', 'DEVUELTO'"


def upgrade() -> None:
    with op.batch_alter_table("tbl_documento_electronico") as batch_op:
        batch_op.drop_constraint("ck_tbl_documento_electronico_estado", type_="check")
        batch_op.alter_column(
            "venta_id",
            existing_type=sa.Uuid(),
            nullable=True,
        )
        batch_op.alter_column(
            "clave_acceso",
            existing_type=sa.String(length=49),
            nullable=True,
        )
        batch_op.add_column(
            sa.Column("tipo_documento", sa.String(length=20), nullable=False, server_default="FACTURA")
        )
        batch_op.add_column(sa.Column("referencia_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("estado_sri", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("mensajes_sri", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("xml_autorizado", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("intentos", sa.Integer(), nullable=False, server_default=sa.text("0"))
        )
        batch_op.add_column(sa.Column("next_retry_at", sa.DateTime(), nullable=True))
        batch_op.add_column(
            sa.Column("cantidad_impresiones", sa.Integer(), nullable=False, server_default=sa.text("0"))
        )

    op.execute("UPDATE tbl_documento_electronico SET referencia_id = venta_id WHERE referencia_id IS NULL")
    op.execute("UPDATE tbl_documento_electronico SET estado_sri = estado WHERE estado_sri IS NULL")
    op.execute(
        "UPDATE tbl_documento_electronico SET tipo_documento = 'FACTURA' "
        "WHERE tipo_documento IS NULL OR trim(tipo_documento) = ''"
    )

    with op.batch_alter_table("tbl_documento_electronico") as batch_op:
        batch_op.alter_column(
            "estado_sri",
            existing_type=sa.String(length=20),
            nullable=False,
            server_default="ENVIADO",
        )
        batch_op.create_check_constraint(
            "ck_tbl_documento_electronico_estado",
            f"estado IN ({CURRENT_DOCUMENT_STATES})",
        )

    op.create_index("ix_tbl_documento_electronico_tipo_documento", "tbl_documento_electronico", ["tipo_documento"])
    op.create_index("ix_tbl_documento_electronico_referencia_id", "tbl_documento_electronico", ["referencia_id"])
    op.create_index("ix_tbl_documento_electronico_next_retry_at", "tbl_documento_electronico", ["next_retry_at"])


def downgrade() -> None:
    connection = op.get_bind()
    incompatible_documents = connection.execute(
        sa.text(
            "SELECT count(*) FROM tbl_documento_electronico "
            "WHERE tipo_documento <> 'FACTURA' "
            "OR venta_id IS NULL "
            "OR estado NOT IN ('ENVIADO', 'AUTORIZADO', 'RECHAZADO')"
        )
    ).scalar_one()
    if incompatible_documents:
        raise RuntimeError(
            "Cannot downgrade electronic document schema while non-legacy documents or states exist."
        )

    op.drop_index("ix_tbl_documento_electronico_next_retry_at", table_name="tbl_documento_electronico")
    op.drop_index("ix_tbl_documento_electronico_referencia_id", table_name="tbl_documento_electronico")
    op.drop_index("ix_tbl_documento_electronico_tipo_documento", table_name="tbl_documento_electronico")

    with op.batch_alter_table("tbl_documento_electronico") as batch_op:
        batch_op.drop_constraint("ck_tbl_documento_electronico_estado", type_="check")
        batch_op.create_check_constraint(
            "ck_tbl_documento_electronico_estado",
            "estado IN ('ENVIADO', 'AUTORIZADO', 'RECHAZADO')",
        )
        batch_op.alter_column(
            "venta_id",
            existing_type=sa.Uuid(),
            nullable=False,
        )
        batch_op.alter_column(
            "clave_acceso",
            existing_type=sa.String(length=49),
            nullable=False,
        )
        for column in (
            "cantidad_impresiones",
            "next_retry_at",
            "intentos",
            "xml_autorizado",
            "mensajes_sri",
            "estado_sri",
            "referencia_id",
            "tipo_documento",
        ):
            batch_op.drop_column(column)
