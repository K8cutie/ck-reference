# backend/scripts/smoke_books_export.py
"""
Smoke test for /compliance/books/export

Checks:
1) GET /compliance/books/export?date_from=2025-08-01&date_to=2025-08-31 returns application/zip
2) ZIP contains: general_journal.csv, general_ledger.csv, cash_receipts_book.csv, cash_disbursements_book.csv
3) general_journal.csv includes our reference LOCKTEST-001
"""

import io
import sys
import csv
import zipfile
import requests

BASE = "http://127.0.0.1:8000"
DATE_FROM = "2025-08-01"
DATE_TO = "2025-08-31"
REF = "LOCKTEST-001"

def main():
    r = requests.get(f"{BASE}/compliance/books/export", params={"date_from": DATE_FROM, "date_to": DATE_TO})
    if r.status_code != 200:
        raise SystemExit(f"export HTTP {r.status_code}: {r.text}")
    ctype = r.headers.get("content-type", "")
    if not ctype.startswith("application/zip"):
        raise SystemExit(f"unexpected content-type: {ctype}")

    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(z.namelist())

    required = {
        "general_journal.csv",
        "general_ledger.csv",
        "cash_receipts_book.csv",
        "cash_disbursements_book.csv",
    }
    missing = required - names
    if missing:
        raise SystemExit(f"missing in ZIP: {sorted(missing)}; found={sorted(names)}")

    # Check our reference in General Journal
    gj_bytes = z.read("general_journal.csv")
    gj_text = gj_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(gj_text))
    hits = [row for row in reader if (row.get("reference") == REF)]
    if not hits:
        # Dump first few rows to help debug
        r = csv.DictReader(io.StringIO(gj_text))
        sample = [next(r) for _ in range(3)]
        raise SystemExit(f"reference {REF} not found in general_journal.csv; sample={sample}")

    print("✅ SMOKE OK: books export ZIP valid; LOCKTEST-001 present in general_journal.csv")

if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        print(f"❌ SMOKE FAIL: {e}", file=sys.stderr)
        sys.exit(1)
