"""Add sigma_logs table (idempotent)."""

from alembic import op

# Revision identifiers, used by Alembic.
revision = "fb22fafa61a6"
down_revision = "77c6958025b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the table only if it doesn't already exist (handles pre-existing DBs)
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.sigma_logs') IS NULL THEN
                CREATE TABLE public.sigma_logs (
                    id UUID PRIMARY KEY NOT NULL,
                    process VARCHAR(100) NOT NULL,
                    ctq VARCHAR(100),
                    period_start TIMESTAMPTZ NOT NULL,
                    period_end TIMESTAMPTZ NOT NULL,
                    units INTEGER NOT NULL,
                    opportunities_per_unit INTEGER NOT NULL,
                    defects INTEGER NOT NULL,
                    notes TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    # Drop the table only if it exists
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.sigma_logs') IS NOT NULL THEN
                DROP TABLE public.sigma_logs;
            END IF;
        END
        $$;
        """
    )
