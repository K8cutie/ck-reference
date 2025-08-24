# scripts/heal_rbac_now.py
"""
Heals RBAC tables in the CURRENT DATABASE_URL without touching Alembic state.
Safe/idempotent: creates missing tables, indexes, and the CHECK constraint.

Usage:
  (.venv) PS C:\\ckchurch1\\backend> python scripts/heal_rbac_now.py
"""
from __future__ import annotations

import os
import sys
from sqlalchemy import create_engine, text


DDL = """
-- ROLES -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.roles (
    id UUID PRIMARY KEY NOT NULL,
    name VARCHAR(50) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(name)
);

-- USERS -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY NOT NULL,
    email VARCHAR(255) NOT NULL,
    display_name VARCHAR(100),
    api_key_hash VARCHAR(128),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(email)
);

-- USER_ROLES ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.user_roles (
    user_id UUID NOT NULL,
    role_id UUID NOT NULL,
    PRIMARY KEY (user_id, role_id),
    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE
);

-- ROLE_PERMISSIONS ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.role_permissions (
    role_id UUID NOT NULL,
    permission VARCHAR(100) NOT NULL,
    PRIMARY KEY (role_id, permission),
    FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE
);

-- CHECK constraint for non-empty permission (needs DO block for IF NOT EXISTS)
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

-- Indexes (idempotent) --------------------------------------------------------
CREATE INDEX IF NOT EXISTS ix_users_email ON public.users (email);
CREATE INDEX IF NOT EXISTS ix_users_api_key_hash ON public.users (api_key_hash);
CREATE INDEX IF NOT EXISTS ix_roles_name ON public.roles (name);
"""


def main() -> int:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL is not set.", file=sys.stderr)
        return 2

    print(f"🔗 Healing RBAC in DB: {db_url}")
    engine = create_engine(db_url, pool_pre_ping=True, future=True)

    with engine.begin() as conn:
        conn.execute(text(DDL))

        # Show what exists now
        roles = conn.execute(text("SELECT to_regclass('public.roles')")).scalar_one()
        users = conn.execute(text("SELECT to_regclass('public.users')")).scalar_one()
        uroles = conn.execute(text("SELECT to_regclass('public.user_roles')")).scalar_one()
        rperms = conn.execute(text("SELECT to_regclass('public.role_permissions')")).scalar_one()
        print(f"✅ roles: {bool(roles)}, users: {bool(users)}, user_roles: {bool(uroles)}, role_permissions: {bool(rperms)}")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
