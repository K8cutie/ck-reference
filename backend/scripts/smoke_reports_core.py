# backend/scripts/smoke_reports_core.py
"""
Smoke test for core reports:
1) Trial Balance (TB) zero-sum within a date range
2) Income Statement (P&L) returns 200 + JSON
3) Balance Sheet (BS) returns 200 + JSON

Note: We only assert TB zero-sum. P&L/BS are printed for inspection
because equality to A = L + E may depend on opening balances/closing entries.

Run:
(.venv) > python backend/scripts/smoke_reports_core.py
"""

import sys
import decimal
import requests

BASE = "http://127.0.0.1:8000"
DATE_FROM = "2025-08-01"
DATE_TO = "2025-08-31"
AS_OF = "2025-08-31"

def get_json(path, params=None):
    r = requests.get(f"{BASE}{path}", params=params or {})
    if r.status_code != 200:
        raise SystemExit(f"GET {path} -> {r.status_code}: {r.text}")
    return r.json()

def main():
    # 1) Trial Balance zero-sum
    tb = get_json(
        "/gl/reports/trial_balance",
        params={"date_from": DATE_FROM, "date_to": DATE_TO},
    )
    rows = tb.get("rows", [])
    sum_dr = decimal.Decimal("0")
    sum_cr = decimal.Decimal("0")
    for r in rows:
        sum_dr += decimal.Decimal(str(r.get("debit", 0) or 0))
        sum_cr += decimal.Decimal(str(r.get("credit", 0) or 0))
    diff = (sum_dr - sum_cr).quantize(decimal.Decimal("0.01"))
    if diff != decimal.Decimal("0.00"):
        raise SystemExit(f"TB not zero-sum: totalDr={sum_dr} totalCr={sum_cr} diff={diff}")

    # 2) Income Statement reachability
    pl = get_json(
        "/gl/reports/income_statement",
        params={"date_from": DATE_FROM, "date_to": DATE_TO},
    )
    totals = pl.get("totals", {})
    income_total = totals.get("income_total", 0)
    expense_total = totals.get("expense_total", 0)
    net_income = totals.get("net_income", 0)

    # 3) Balance Sheet reachability
    bs = get_json("/gl/reports/balance_sheet", params={"as_of": AS_OF})
    bs_totals = bs.get("totals", {})
    assets = bs_totals.get("assets", 0)
    liab = bs_totals.get("liabilities", 0)
    eq = bs_totals.get("equity", 0)

    print("✅ SMOKE OK: TB zero-sum for", DATE_FROM, "to", DATE_TO)
    print(f"ℹ️ P&L totals: income={income_total} expense={expense_total} net={net_income}")
    print(f"ℹ️ BS totals (as_of {AS_OF}): assets={assets} liabilities={liab} equity={eq} (A vs L+E not enforced here)")

if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        print(f"❌ SMOKE FAIL: {e}", file=sys.stderr)
        sys.exit(1)
