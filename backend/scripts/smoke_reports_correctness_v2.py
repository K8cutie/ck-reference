# scripts/smoke_reports_correctness_v2.py
from __future__ import annotations
import os, sys, json
from datetime import datetime, date
from decimal import Decimal
import requests

BASE = os.getenv("BASE", "http://127.0.0.1:8000")

def req(m, path, ok=200, **kw):
    r = requests.request(m, f"{BASE}{path}", timeout=60, **kw)
    ct = r.headers.get("content-type","")
    body = r.json() if ct.startswith("application/json") else r.text
    if r.status_code != ok:
        raise SystemExit(f"{m} {path} -> {r.status_code}: {body}")
    return body

def last_dom(y, m):
    for d in (31,30,29,28):
        try: date(y,m,d); return d
        except ValueError: pass
    return 28

D = lambda x: Decimal(str(x))

def fetch_all_accounts():
    out, offset = [], 0
    while True:
        chunk = req("GET", "/gl/accounts", params={"limit": 200, "offset": offset})
        if not chunk: break
        out.extend(chunk)
        if len(chunk) < 200: break
        offset += len(chunk)
    return out

def fetch_all_journal_entries(date_from: str, date_to: str):
    out, offset = [], 0
    while True:
        chunk = req("GET", "/gl/journal", params={
            "date_from": date_from, "date_to": date_to, "is_locked": True,
            "limit": 200, "offset": offset
        })
        if not chunk: break
        out.extend(chunk)
        if len(chunk) < 200: break
        offset += len(chunk)
    return out

def fetch_latest_closing(close_ref: str):
    # paginate all closings for this ref; pick the highest id (latest)
    out, offset = [], 0
    while True:
        chunk = req("GET", "/gl/journal", params={
            "reference_no": close_ref, "is_locked": True, "limit": 200, "offset": offset
        })
        if not chunk: break
        out.extend(chunk)
        if len(chunk) < 200: break
        offset += len(chunk)
    if not out:
        return None
    return max(out, key=lambda je: int(je.get("id", 0)))

def main():
    now = datetime.now(); y, m = now.year, now.month
    first = date(y, m, 1).isoformat()
    last  = date(y, m, last_dom(y, m)).isoformat()
    period = f"{y:04d}-{m:02d}"
    close_ref = f"CLOSE-{y:04d}{m:02d}"

    # accounts (id -> type), equity id set
    accts = fetch_all_accounts()
    id_type = {int(a["id"]): (a.get("type") or "").lower() for a in accts}
    equity_ids = {aid for aid, t in id_type.items() if t == "equity"}

    # posted journal entries for month (exclude OPEN/CLOSE in aggregation)
    jes = fetch_all_journal_entries(first, last)

    debs = Decimal("0"); creds = Decimal("0")
    inc_net = Decimal("0"); exp_net = Decimal("0")

    for je in jes:
        ref = je.get("reference_no") or ""
        if isinstance(ref, str) and (ref.startswith("OPEN-") or ref.startswith("CLOSE-")):
            continue
        for ln in je.get("lines", []):
            dr = D(ln.get("debit") or 0); cr = D(ln.get("credit") or 0)
            debs += dr; creds += cr
            t = id_type.get(int(ln.get("account_id")), "")
            if t == "income":
                inc_net += (cr - dr)
            elif t == "expense":
                exp_net += (dr - cr)

    if (debs - creds).copy_abs() > Decimal("0.01"):
        raise SystemExit(f"❌ Zero-sum fail {period}: debits={debs} credits={creds}")

    # latest closing (by id) and its equity amount
    closing = fetch_latest_closing(close_ref)
    if not closing:
        raise SystemExit(f"❌ No closing JE found for {period} ({close_ref}).")

    eq_net = Decimal("0")
    for ln in closing.get("lines", []):
        if int(ln.get("account_id")) in equity_ids:
            eq_net += (D(ln.get("credit") or 0) - D(ln.get("debit") or 0))

    net_income = inc_net - exp_net
    if (eq_net - net_income).copy_abs() > Decimal("0.01"):
        detail = {
            "period": period,
            "net_income": str(net_income),
            "equity_on_close": str(eq_net),
            "close_ref": close_ref,
            "closing_je_id": int(closing.get("id")),
            "debits": str(debs), "credits": str(creds),
            "entries_analyzed": len(jes), "accounts_count": len(accts),
        }
        raise SystemExit("❌ P&L vs CLOSE mismatch:\n" + json.dumps(detail, indent=2))

    summary = {
        "period": period,
        "zero_sum": {"debits": str(debs), "credits": str(creds)},
        "pnl_equals_close": {
            "net_income": str(net_income),
            "equity_on_close": str(eq_net),
            "close_ref": close_ref,
            "closing_je_id": int(closing.get("id")),
        },
        "entries_analyzed": len(jes),
        "accounts_count": len(accts),
    }
    print("✅ REPORTS CORRECTNESS OK")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    try: main()
    except SystemExit as e:
        print(e, file=sys.stderr); sys.exit(1)
