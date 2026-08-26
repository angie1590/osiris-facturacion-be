"""expand audit_log standard fields

Revision ID: 3c8d2e7a4b11
Revises: 9d4b6f2a1c33
Create Date: 2026-02-19 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3c8d2e7a4b11"
down_revision: Union[str, None] = "9d4b6f2a1c33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("audit_log", sa.Column("tabla_afectada", sa.String(length=100), nullable=True))
    op.add_column("audit_log", sa.Column("registro_id", sa.String(length=120), nullable=True))
    op.add_column("audit_log", sa.Column("usuario_id", sa.String(length=255), nullable=True))
    op.add_column(
        "audit_log",
        sa.Column("fecha", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.execute(
        """
        UPDATE audit_log
        SET tabla_afectada = COALESCE(tabla_afectada, entidad),
            registro_id = COALESCE(registro_id, CAST(entidad_id AS TEXT)),
            usuario_id = COALESCE(usuario_id, updated_by, created_by, usuario_auditoria),
            fecha = COALESCE(fecha, creado_en)
        """
    )

    op.create_index("ix_audit_log_tabla_afectada", "audit_log", ["tabla_afectada"], unique=False)
    op.create_index("ix_audit_log_registro_id", "audit_log", ["registro_id"], unique=False)
    op.create_index("ix_audit_log_usuario_id", "audit_log", ["usuario_id"], unique=False)
    op.create_index("ix_audit_log_fecha", "audit_log", ["fecha"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_log_fecha", table_name="audit_log")
    op.drop_index("ix_audit_log_usuario_id", table_name="audit_log")
    op.drop_index("ix_audit_log_registro_id", table_name="audit_log")
    op.drop_index("ix_audit_log_tabla_afectada", table_name="audit_log")
    op.drop_column("audit_log", "fecha")
    op.drop_column("audit_log", "usuario_id")
    op.drop_column("audit_log", "registro_id")
    op.drop_column("audit_log", "tabla_afectada")
