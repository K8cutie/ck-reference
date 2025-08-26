# Smoke for /gl/close-range and /gl/reopen-range
# Now: expected RED (404) until endpoints exist.
# After patch: expect 200 with summary `results`.

import os, sys, json
from datetime import datetime
import requests

BASE = os.getenv("BASE", "http://127.0.0.1:8000")

def req(m, path, ok=200, **kw):
    r = requests.request(m, f"{BASE}{path}", timeout=60, **kw)
    ct = r.headers.get("content-type","")
    body = r.json() if ct.startswith("application/json") else r.text
    if r.status_code != ok:
        raise SystemExit(f"{m} {path} -> {r.status_code}: {body}")
    return body

def prev_month(dt):
    y, m = dt.year, dt.month
    return (y-1, 12) if m == 1 else (y, m-1)

if __name__ == "__main__":
    now = datetime.now()
    sy, sm = prev_month(now)     # previous month
    ey, em = now.year, now.month # this month
    start = f"{sy:04d}-{sm:02d}"
    end   = f"{ey:04d}-{em:02d}"

    # try reopen-range (idempotent) then close-range
    out1 = req("POST", f"/gl/reopen-range/{start}/{end}")
    print("✅ reopen-range responded")
    print(json.dumps(out1, indent=2, default=str))

    # equity_account_id can be omitted if service can auto-pick; here we omit
    out2 = req("POST", f"/gl/close-range/{start}/{end}")
    print("✅ close-range responded")
    print(json.dumps(out2, indent=2, default=str))
