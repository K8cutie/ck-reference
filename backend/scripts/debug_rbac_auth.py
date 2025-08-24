# scripts/debug_rbac_auth.py
"""
Quick check: does the current DATABASE_URL contain a user row matching the given API key?
- Uses raw SQL (no ORM imports).
- Prints DB URL (masked), computed hash, and the matched user (if any).

Usage:
  (.venv) PS C:\ckchurch1\backend> python scripts/debug_rbac_auth.py --api-key "<PASTE_YOUR_API_KEY>"
"""
from __future__ import annotations

import argparse
import os
import sys
import hashlib
from sqlalchemy import create_engine, text

def mask_db_url(url: str) -> str:
    # very basic mask for display
    if "@" in url:
        before, after = url.split("@", 1)
        return "***@" + after
    return url

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", required=True, help="Plaintext API key to verify")
    args = parser.parse_args()

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL is not set.", file=sys.stderr)
        return 2

    print(f"🔗 Using DATABASE_URL: {mask_db_url(db_url)}")

    # Hash the provided key (same logic as app + seed; no pepper assumed here)
    pepper = os.getenv("API_KEY_PEPPER", "")
    h = hashlib.sha256()
    h.update((args.api_key + pepper).encode("utf-8"))
    api_hash = h.hexdigest()
    print(f"🔑 Computed hash: {api_hash}")

    engine = create_engine(db_url, pool_pre_ping=True, future=True)

    with engine.begin() as conn:
        # Ensure table exists
        exists = conn.execute(
            text("SELECT to_regclass('public.users')")
        ).scalar_one()
        print(f"📦 users table present: {bool(exists)}")

        # Try to find the user by hash
        row = conn.execute(
            text("SELECT id, email FROM users WHERE api_key_hash = :h LIMIT 1"),
            {"h": api_hash},
        ).first()

        if row:
            print(f"✅ MATCH: id={row.id}, email={row.email}")
            return 0
        else:
            # Also show total users to help diagnose
            total = conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one()
            print(f"❌ No match for this hash. users.count={total}")
            return 1

if __name__ == "__main__":
    raise SystemExit(main())
