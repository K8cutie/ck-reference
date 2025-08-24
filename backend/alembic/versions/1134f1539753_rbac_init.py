"""Enforce non-empty permission strings on role_permissions.

Revision ID: 1134f1539753
Revises: b9a3d1f42c77
Create Date: 2025-08-10
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "1134f1539753"
down_revision: Union[str, Sequence[str], None] = "b9a3d1f42c77"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add CHECK constraint if missing (idempotent for Postgres)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                WHERE t.relname = 'role_permissions'
                  AND c.conname = 'ck_role_permissions_perm_not_empty'
            ) THEN
                ALTER TABLE role_permissions
                ADD CONSTRAINT ck_role_permissions_perm_not_empty
                CHECK (length(permission) > 0);
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    # Drop CHECK constraint if present
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                WHERE t.relname = 'role_permissions'
                  AND c.conname = 'ck_role_permissions_perm_not_empty'
            ) THEN
                ALTER TABLE role_permissions
                DROP CONSTRAINT ck_role_permissions_perm_not_empty;
            END IF;
        END
        $$;
        """
    )
