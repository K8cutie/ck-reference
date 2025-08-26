# Smoke for /gl/reclose-range/{start}/{end}
# Now: expected RED (404) until the endpoint exists.
# After we add the API, this should go GREEN (200) with a summary result.

import os, sys, json
from datetime import datetime
import requests

BASE = os.getenv("BASE", "http://127.0.0.1:8000")
ADMIN_KEY = os.getenv("CK_ADMIN_KEY")  # if your API needs X-API-Key

def req(m, path, ok=200, **kw):
    url = f"{BASE}{path}"
    headers = kw.pop("headers", {})
    if ADMIN_KEY:
        headers["X-API-Key"] = ADMIN_KEY
    r = requests.request(m, url, headers=headers, timeout=60, **kw)
    ct = r.headers.get("content-type", "")
    body = r.json() if ct.startswith("application/json") else r.text
    if r.status_code != ok:
        raise SystemExit(f"{m} {path} -> {r.status_code}: {body}")
    return body

def prev_month_str(dt):
    y, m = dt.year, dt.month
    y, m = (y-1, 12) if m == 1 else (y, m-1)
    return f"{y:04d}-{m:02d}"

def main():
    now = datetime.now()
    start = prev_month_str(now)      # previous month
    end = now.strftime("%Y-%m")      # this month
    out = req("POST", f"/gl/reclose-range/{start}/{end}", ok=200)
    print("✅ RANGE SMOKE OK")
    print(json.dumps(out, indent=2, default=str))

if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        print(f"❌ SMOKE FAIL: {e}", file=sys.stderr)
        sys.exit(1)
