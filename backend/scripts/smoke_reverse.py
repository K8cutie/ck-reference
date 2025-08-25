# backend/scripts/smoke_reverse.py
"""
Smoke test for reversal:
- Ensure there is a POSTED JE (create+post one if needed)
- Call /gl/journal/{id}/reverse
- Verify Books (General Journal) nets to zero across source and reversal

Run:
(.venv) > python backend/scripts/smoke_reverse.py
"""

import sys
import time
from datetime import date, datetime
import decimal
import requests

BASE = "http://127.0.0.1:8000"

def req(method, path, ok=200, **kwargs):
    r = requests.request(method, f"{BASE}{path}", **kwargs)
    if r.status_code != ok:
        raise SystemExit(f"{method} {path} -> {r.status_code}: {r.text}")
    if r.headers.get("content-type","").startswith("application/json"):
        return r.json()
    return r.text

def ensure_unlocked(y: int, m: int):
    # unlock month (idempotent)
    req("DELETE", f"/gl/locks/{y:04d}-{m:02d}")

def pick_accounts():
    accts = req("GET", "/gl/accounts", params={"limit": 200})
    if not accts:
        raise SystemExit("No GL accounts available.")
    debit = next((a["id"] for a in accts if a.get("is_cash")), accts[0]["id"])
    credit = next((a["id"] for a in accts if a["id"] != debit), accts[-1]["id"])
    return debit, credit

def ensure_posted_je():
    posted = req("GET", "/gl/journal", params={"is_locked": True, "limit": 100})
    if posted:
        return posted[-1]  # most recent
    # else create one now (today)
    today = date.today()
    ensure_unlocked(today.year, today.month)
    debit, credit = pick_accounts()
    ref = f"REVSMOKE-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    body = {
        "entry_date": today.isoformat(),
        "memo": "reversal smoke source",
        "currency_code": "PHP",
        "reference_no": ref,
        "source_module": "smoke",
        "source_id": ref,
        "lines": [
            {"account_id": debit, "description": "dr", "debit": 321, "credit": 0},
            {"account_id": credit, "description": "cr", "debit": 0, "credit": 321},
        ],
    }
    je = req("POST", "/gl/journal", json=body)
    # post it
    je = req("POST", f"/gl/journal/{je['id']}/post")
    return je

def sum_net_for_refs(refs, date_from, date_to):
    gj = req("GET", "/compliance/books/view/general_journal",
             params={"date_from": date_from, "date_to": date_to})
    rows = [r for r in gj["rows"] if r.get("reference") in refs]
    net = decimal.Decimal("0")
    for r in rows:
        net += decimal.Decimal(str(r.get("debit", 0) or 0))
        net -= decimal.Decimal(str(r.get("credit", 0) or 0))
    return rows, net

def main():
    src = ensure_posted_je()
    src_ref = src.get("reference_no") or f"JE-{src.get('entry_no')}"
    src_date = date.fromisoformat(src["entry_date"])

    # reversal date = src_date (default); ensure month is unlocked
    ensure_unlocked(src_date.year, src_date.month)

    # call reverse
    rev = req("POST", f"/gl/journal/{src['id']}/reverse")
    assert rev["is_locked"] is True, rev
    rev_ref = rev.get("reference_no", "")

    # verify Books net zero across source + reversal for the month window
    date_from = src_date.replace(day=1).isoformat()
    # rough end-of-month (safe enough for smoke)
    if src_date.month == 12:
        date_to = src_date.replace(year=src_date.year+1, month=1, day=1).isoformat()
    else:
        date_to = src_date.replace(month=src_date.month+1, day=1).isoformat()

    rows, net = sum_net_for_refs({src_ref, rev_ref}, date_from, date_to)

    if net != decimal.Decimal("0"):
        raise SystemExit(f"Books not net-zero for refs {src_ref},{rev_ref}: net={net}, rows={rows[:4]}")

    print(f"✅ SMOKE OK: reversal created (src={src['id']} -> rev={rev['id']}); Books net to zero for refs {src_ref} & {rev_ref}")

if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        print(f"❌ SMOKE FAIL: {e}", file=sys.stderr)
        sys.exit(1)
