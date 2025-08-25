# backend/scripts/smoke_gl_locks.py
"""
Smoke test for GL period locks + post/unpost behavior.

What it does:
1) PUT /gl/locks/2025-08         -> lock month
2) POST /gl/journal               -> create balanced JE in August 2025
3) POST /gl/journal/{id}/post     -> expect 400 (locked)
4) DELETE /gl/locks/2025-08       -> unlock
5) POST /gl/journal/{id}/post     -> expect 200 (posted)
6) PUT /gl/locks/2025-08          -> lock again
7) POST /gl/journal/{id}/unpost   -> expect 400 (locked)
8) Print PASS summary

Run:
(.venv) > python backend/scripts/smoke_gl_locks.py
"""

import json
import sys
from datetime import datetime
import requests

BASE = "http://127.0.0.1:8000"

def req(method, path, ok=200, **kwargs):
    url = f"{BASE}{path}"
    r = requests.request(method, url, **kwargs)
    if r.status_code != ok:
        # Try to show server error JSON if present
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise SystemExit(f"{method} {path} -> {r.status_code}: {detail}")
    if r.headers.get("content-type", "").startswith("application/json"):
        return r.json()
    return r.text

def main():
    # 1) Lock month
    lock = req("PUT", "/gl/locks/2025-08", params={"note": "smoke"})
    assert lock["is_locked"] is True and lock["period_month"].startswith("2025-08"), lock

    # 2) Create balanced JE in locked month
    # Find two accounts
    accts = req("GET", "/gl/accounts", params={"limit": 100})
    if not accts:
        raise SystemExit("No GL accounts exist. Create at least two accounts first.")
    debit = next((a["id"] for a in accts if a.get("is_cash")), accts[0]["id"])
    credit = next((a["id"] for a in accts if a["id"] != debit), accts[1]["id"])

    ref = f"SMOKE-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    body = {
        "entry_date": "2025-08-15",
        "memo": "smoke lock guard",
        "currency_code": "PHP",
        "reference_no": ref,
        "source_module": "smoke",
        "source_id": ref,
        "lines": [
            {"account_id": debit, "description": "dr", "debit": 100, "credit": 0},
            {"account_id": credit, "description": "cr", "debit": 0, "credit": 100},
        ],
    }
    je = req("POST", "/gl/journal", json=body)
    je_id = je["id"]

    # 3) Try post -> expect 400 (locked)
    r = requests.post(f"{BASE}/gl/journal/{je_id}/post")
    if r.status_code == 200:
        raise SystemExit(f"Expected 400 on post while locked; got 200: {r.json()}")
    j = r.json()
    assert "Cannot post: period 2025-08 is locked." in json.dumps(j), j

    # 4) Unlock -> expect 200
    unlock = req("DELETE", "/gl/locks/2025-08")
    assert unlock["is_locked"] is False, unlock

    # 5) Post -> expect 200 and is_locked true
    posted = req("POST", f"/gl/journal/{je_id}/post")
    assert posted["is_locked"] is True and posted["posted_at"], posted

    # 6) Lock again
    lock2 = req("PUT", "/gl/locks/2025-08", params={"note": "smoke re-lock"})
    assert lock2["is_locked"] is True, lock2

    # 7) Try unpost -> expect 400 (locked)
    r2 = requests.post(f"{BASE}/gl/journal/{je_id}/unpost")
    if r2.status_code == 200:
        raise SystemExit(f"Expected 400 on unpost while locked; got 200: {r2.json()}")
    j2 = r2.json()
    assert "Cannot unpost: period 2025-08 is locked." in json.dumps(j2), j2

    print("✅ SMOKE OK: locks/post/unpost guardrails working.")

if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        print(f"❌ SMOKE FAIL: {e}", file=sys.stderr)
        sys.exit(1)
