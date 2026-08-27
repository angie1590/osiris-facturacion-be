"""add created_by updated_by columns

Revision ID: 9d4b6f2a1c33
Revises: 7a1c9d4e2f10
Create Date: 2026-02-19 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "9d4b6f2a1c33"
down_revision: Union[str, None] = "7a1c9d4e2f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    DO $$
    DECLARE table_record record;
    BEGIN
        FOR table_record IN
            SELECT DISTINCT table_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND column_name = 'usuario_auditoria'
        LOOP
            EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS created_by VARCHAR(255)', table_record.table_name);
            EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS updated_by VARCHAR(255)', table_record.table_name);
            EXECUTE format('UPDATE %I SET created_by = COALESCE(created_by, usuario_auditoria), updated_by = COALESCE(updated_by, usuario_auditoria)', table_record.table_name);
            EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (created_by)', 'ix_' || table_record.table_name || '_created_by', table_record.table_name);
            EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (updated_by)', 'ix_' || table_record.table_name || '_updated_by', table_record.table_name);
        END LOOP;
    END $$;
    """)


def downgrade() -> None:
    op.execute("""
    DO $$
    DECLARE table_record record;
    BEGIN
        FOR table_record IN
            SELECT DISTINCT table_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND column_name = 'usuario_auditoria'
        LOOP
            EXECUTE format('DROP INDEX IF EXISTS %I', 'ix_' || table_record.table_name || '_created_by');
            EXECUTE format('DROP INDEX IF EXISTS %I', 'ix_' || table_record.table_name || '_updated_by');
            EXECUTE format('ALTER TABLE %I DROP COLUMN IF EXISTS updated_by', table_record.table_name);
            EXECUTE format('ALTER TABLE %I DROP COLUMN IF EXISTS created_by', table_record.table_name);
        END LOOP;
    END $$;
    """)
