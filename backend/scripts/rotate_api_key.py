# scripts/rotate_api_key.py
"""
Rotate API key for an existing user (DB-only, raw SQL).
- Uses DATABASE_URL and API_KEY_PEPPER from the current shell.
- Prints the NEW plaintext API key exactly once.

Usage (PowerShell, same shell you'll test from):
  $env:DATABASE_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/ckchurch"
  $env:API_KEY_PEPPER = ""  # or your actual pepper, must match server
  python scripts/rotate_api_key.py --email admin@clearkeep.local
"""
from __future__ import annotations

import argparse
import hashlib
import os
import secrets
import sys

from sqlalchemy import create_engine, text


def hash_key(plain: str) -> str:
    pepper = os.getenv("API_KEY_PEPPER", "")
    h = hashlib.sha256()
    h.update((plain + pepper).encode("utf-8"))
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Rotate API key for an existing user")
    parser.add_argument("--email", required=True, help="User email to rotate key for")
    args = parser.parse_args()

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL is not set.", file=sys.stderr)
        return 2

    email = args.email.strip().lower()
    new_key = secrets.token_urlsafe(32)
    new_hash = hash_key(new_key)

    engine = create_engine(db_url, pool_pre_ping=True, future=True)
    with engine.begin() as conn:
        row = conn.execute(
            text("UPDATE users SET api_key_hash=:h, is_active=TRUE WHERE lower(email)=:e RETURNING id"),
            {"h": new_hash, "e": email},
        ).first()
        if not row:
            print(f"ERROR: user '{email}' not found.", file=sys.stderr)
            return 1

    print("\n✅ API key rotated.")
    print(f"   email: {email}")
    print("\n⚠️  SAVE THIS API KEY NOW (shown only once):")
    print(f"   API KEY: {new_key}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
