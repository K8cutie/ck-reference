"""Heal RBAC tables idempotently (creates any missing RBAC tables/constraints/indexes).

This migration is safe to run on databases that already have some of the RBAC tables.
It only creates what's missing and adds indexes/constraints if absent.
"""

from alembic import op

# --- revision identifiers ---
revision = "19624fe98afd"
down_revision = "1134f1539753"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        -- ROLES ---------------------------------------------------------------
        DO $$
        BEGIN
            IF to_regclass('public.roles') IS NULL THEN
                CREATE TABLE public.roles (
                    id UUID PRIMARY KEY NOT NULL,
                    name VARCHAR(50) NOT NULL,
                    description TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    UNIQUE(name)
                );
            END IF;
        END
        $$;

        -- USERS ---------------------------------------------------------------
        DO $$
        BEGIN
            IF to_regclass('public.users') IS NULL THEN
                CREATE TABLE public.users (
                    id UUID PRIMARY KEY NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    display_name VARCHAR(100),
                    api_key_hash VARCHAR(128),
                    is_active BOOLEAN NOT NULL DEFAULT true,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    UNIQUE(email)
                );
            END IF;
        END
        $$;

        -- USER_ROLES ----------------------------------------------------------
        DO $$
        BEGIN
            IF to_regclass('public.user_roles') IS NULL THEN
                CREATE TABLE public.user_roles (
                    user_id UUID NOT NULL,
                    role_id UUID NOT NULL,
                    PRIMARY KEY (user_id, role_id),
                    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE,
                    FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE
                );
            END IF;
        END
        $$;

        -- ROLE_PERMISSIONS ----------------------------------------------------
        DO $$
        BEGIN
            IF to_regclass('public.role_permissions') IS NULL THEN
                CREATE TABLE public.role_permissions (
                    role_id UUID NOT NULL,
                    permission VARCHAR(100) NOT NULL,
                    PRIMARY KEY (role_id, permission),
                    FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE
                );
            END IF;
        END
        $$;

        -- CHECK constraint to keep permission non-empty -----------------------
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                WHERE t.relname = 'role_permissions'
                  AND c.conname = 'ck_role_permissions_perm_not_empty'
            ) THEN
                ALTER TABLE public.role_permissions
                ADD CONSTRAINT ck_role_permissions_perm_not_empty
                CHECK (length(permission) > 0);
            END IF;
        END
        $$;

        -- Indexes (harmless if already present) -------------------------------
        CREATE INDEX IF NOT EXISTS ix_users_email ON public.users (email);
        CREATE INDEX IF NOT EXISTS ix_users_api_key_hash ON public.users (api_key_hash);
        CREATE INDEX IF NOT EXISTS ix_roles_name ON public.roles (name);
        """
    )


def downgrade() -> None:
    # No-op: this migration only heals drift and is safe to keep.
    pass
