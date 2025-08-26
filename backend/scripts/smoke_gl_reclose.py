# backend/scripts/smoke_gl_reclose.py
"""
Smoke for /gl/reclose/{YYYY-MM}

Now: expected to FAIL (404/405) until the API exists.
After we add the endpoint calling services.gl_accounting.reclose_period(...),
this should pass (200).

Run:
  (.venv) > python backend/scripts/smoke_gl_reclose.py
Optional env:
  BASE=http://127.0.0.1:8000
  CK_ADMIN_KEY=<if your API expects X-API-Key>
"""
import os, sys, json
from datetime import datetime
import requests

BASE = os.getenv("BASE", "http://127.0.0.1:8000")
ADMIN_KEY = os.getenv("CK_ADMIN_KEY")

def req(m, path, ok=200, **kw):
    url = f"{BASE}{path}"
    headers = kw.pop("headers", {})
    if ADMIN_KEY:
        headers["X-API-Key"] = ADMIN_KEY
    r = requests.request(m, url, headers=headers, timeout=30, **kw)
    ct = r.headers.get("content-type", "")
    body = r.json() if ct.startswith("application/json") else r.text
    if r.status_code != ok:
        raise SystemExit(f"{m} {path} -> {r.status_code}: {body}")
    return body

def main():
    period = datetime.now().strftime("%Y-%m")
    out = req("POST", f"/gl/reclose/{period}", ok=200, json={"note": "smoke reclose"})
    print("✅ SMOKE OK: /gl/reclose returned 200")
    if isinstance(out, dict):
        print(json.dumps(out, indent=2, default=str))
    else:
        print(out)

if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        print(f"❌ SMOKE FAIL: {e}", file=sys.stderr)
        sys.exit(1)
