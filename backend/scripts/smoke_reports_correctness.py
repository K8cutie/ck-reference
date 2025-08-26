from __future__ import annotations
import os, sys, json
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
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

D = lambda x: Decimal(str(x)) if not isinstance(x, Decimal) else x

def main():
    now = datetime.now(); y, m = now.year, now.month
    first = date(y, m, 1); last = date(y, m, last_dom(y, m))
    period = f"{y:04d}-{m:02d}"; close_ref = f"CLOSE-{y:04d}{m:02d}"

    # accounts
    accts = req("GET", "/gl/accounts?limit=1000")
    income, expense, equity_ids = set(), set(), set()
    id_type = {}
    for a in accts:
        t = (a.get("type") or "").lower()
        id_type[int(a["id"])] = t
        if t == "income": income.add(a["code"])
        elif t == "expense": expense.add(a["code"])
        elif t == "equity": equity_ids.add(int(a["id"]))

    # GL rows for month
    gl = req("GET", "/compliance/books/view/general_ledger",
             params={"date_from": first.isoformat(), "date_to": last.isoformat()})
    rows = gl.get("rows", [])

    # zero-sum + P&L (exclude OPEN/CLOSE refs)
    debs = Decimal("0"); creds = Decimal("0")
    inc_net = Decimal("0"); exp_net = Decimal("0")
    for r in rows:
        ref = r.get("reference") or ""
        if isinstance(ref, str) and (ref.startswith("OPEN-") or ref.startswith("CLOSE-")):
            continue
        dr = D(r.get("debit") or 0); cr = D(r.get("credit") or 0)
        debs += dr; creds += cr
        code = (r.get("account_code") or "").strip()
        if code in income: inc_net += (cr - dr)
        elif code in expense: exp_net += (dr - cr)

    if (debs - creds).copy_abs() > Decimal("0.01"):
        raise SystemExit(f"❌ Zero-sum fail {period}: debits={debs} credits={creds}")

    # closing JE equity amount
    jes = req("GET", "/gl/journal",
              params={"reference_no": close_ref, "is_locked": True, "limit": 5, "offset": 0})
    if not jes:
        raise SystemExit(f"❌ No closing JE found for {period} ({close_ref}).")
    je = jes[-1]
    eq_net = Decimal("0")
    for ln in je.get("lines", []):
        if id_type.get(int(ln.get("account_id"))) == "equity":
            eq_net += (D(ln.get("credit") or 0) - D(ln.get("debit") or 0))

    net_income = inc_net - exp_net
    if (eq_net - net_income).copy_abs() > Decimal("0.01"):
        detail = {"period": period, "income_net": str(inc_net), "expense_net": str(exp_net),
                  "net_income": str(net_income), "equity_on_close": str(eq_net), "close_ref": close_ref,
                  "closing_je_id": int(je.get("id"))}
        raise SystemExit("❌ P&L vs CLOSE mismatch:\n" + json.dumps(detail, indent=2))

    summary = {
        "period": period,
        "zero_sum": {"debits": str(debs), "credits": str(creds)},
        "pnl_equals_close": {"net_income": str(net_income), "equity_on_close": str(eq_net),
                             "close_ref": close_ref, "closing_je_id": int(je.get("id"))},
        "rows_analyzed": len(rows),
    }
    print("✅ REPORTS CORRECTNESS OK")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    try: main()
    except SystemExit as e:
        print(e, file=sys.stderr); sys.exit(1)
