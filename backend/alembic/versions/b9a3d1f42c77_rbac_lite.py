"""RBAC tables (idempotent create)."""

from alembic import op

# Revision identifiers, used by Alembic.
revision = "b9a3d1f42c77"
down_revision = "6f0d3a1c2b34"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # roles (create if missing)
    op.execute(
        """
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
        """
    )

    # users (create if missing)
    op.execute(
        """
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
        """
    )

    # user_roles (create if missing; depends on users/roles)
    op.execute(
        """
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
        """
    )

    # role_permissions (create if missing; depends on roles)
    op.execute(
        """
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
        """
    )

    # indexes (idempotent)
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_email ON public.users (email)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_api_key_hash ON public.users (api_key_hash)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_roles_name ON public.roles (name)")


def downgrade() -> None:
    # drop in dependency order, only if exists
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.role_permissions') IS NOT NULL THEN
                DROP TABLE public.role_permissions;
            END IF;
            IF to_regclass('public.user_roles') IS NOT NULL THEN
                DROP TABLE public.user_roles;
            END IF;
            IF to_regclass('public.roles') IS NOT NULL THEN
                DROP TABLE public.roles;
            END IF;
            IF to_regclass('public.users') IS NOT NULL THEN
                DROP TABLE public.users;
            END IF;
        END
        $$;
        """
    )
