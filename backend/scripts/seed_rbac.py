# scripts/seed_rbac.py
r"""
Seed RBAC without importing ORM models:
- Creates/ensures a role (default: 'admin') with '*' wildcard.
- Creates an admin user if missing and assigns the role.
- Stores only the API key hash; prints plaintext once.

Usage (PowerShell):
  (.venv) PS C:\ckchurch1\backend> python scripts/seed_rbac.py --email admin@clearkeep.local --name "Admin" --role admin

Then test:
  curl -s -H "X-API-Key: <PRINTED_API_KEY>" http://127.0.0.1:8000/rbac/whoami
"""
from __future__ import annotations

import argparse
import os
import secrets
import sys
import uuid
from typing import Optional

from sqlalchemy import create_engine, text


def _hash_api_key(api_key_plain: str) -> str:
    import hashlib
    pepper = os.getenv("API_KEY_PEPPER", "")
    h = hashlib.sha256()
    h.update((api_key_plain + pepper).encode("utf-8"))
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed RBAC admin role and user (raw SQL)")
    parser.add_argument("--email", required=True, help="Admin user email")
    parser.add_argument("--name", default="Admin", help="Admin display name")
    parser.add_argument("--role", default="admin", help="Admin role name")
    args = parser.parse_args()

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL is not set.", file=sys.stderr)
        return 2

    print(f"🔍 DATABASE_URL = {db_url}")

    engine = create_engine(db_url, pool_pre_ping=True, future=True)

    email = args.email.strip().lower()
    role_name = args.role.strip()

    with engine.begin() as conn:
        # 1) Ensure role exists (idempotent)
        role_row = conn.execute(
            text("SELECT id FROM roles WHERE name = :name"),
            {"name": role_name},
        ).first()

        if role_row is None:
            role_id = str(uuid.uuid4())
            conn.execute(
                text("""
                    INSERT INTO roles (id, name, description, created_at, updated_at)
                    VALUES (:id, :name, :desc, NOW(), NOW())
                """),
                {"id": role_id, "name": role_name, "desc": "Superuser role"},
            )
            print(f"Created role '{role_name}'.")
        else:
            role_id = str(role_row[0])

        # 2) Ensure '*' permission on that role
        conn.execute(
            text("""
                INSERT INTO role_permissions (role_id, permission)
                SELECT :rid, :perm
                WHERE NOT EXISTS (
                    SELECT 1 FROM role_permissions
                    WHERE role_id = :rid AND permission = :perm
                )
            """),
            {"rid": role_id, "perm": "*"},
        )

        # 3) If user exists, exit gracefully
        user_row = conn.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": email},
        ).first()

        if user_row is not None:
            print(f"User '{email}' already exists (id={user_row[0]}).")
            print("NOTE: API key is stored hashed; rotate via RBAC API if needed.")
            return 0

        # 4) Create user with a fresh API key (plaintext shown once)
        api_key_plain = secrets.token_urlsafe(32)
        api_key_hash = _hash_api_key(api_key_plain)
        user_id = str(uuid.uuid4())

        conn.execute(
            text("""
                INSERT INTO users (id, email, display_name, api_key_hash, is_active, created_at, updated_at)
                VALUES (:id, :email, :name, :hash, TRUE, NOW(), NOW())
            """),
            {"id": user_id, "email": email, "name": args.name, "hash": api_key_hash},
        )

        # 5) Assign role to user
        conn.execute(
            text("""
                INSERT INTO user_roles (user_id, role_id)
                VALUES (:uid, :rid)
            """),
            {"uid": user_id, "rid": role_id},
        )

        print("\n✅ Admin user created.")
        print(f"   id:       {user_id}")
        print(f"   email:    {email}")
        print(f"   role:     {role_name}")
        print("\n⚠️  SAVE THIS API KEY NOW (shown only once):")
        print(f"   API KEY:  {api_key_plain}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
