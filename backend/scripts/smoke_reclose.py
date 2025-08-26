import os, sys, json
from datetime import datetime
import requests

BASE = os.getenv("BASE", "http://127.0.0.1:8000")
def req(m, path, ok=200, **kw):
    r = requests.request(m, f"{BASE}{path}", timeout=30, **kw)
    ct = r.headers.get("content-type","")
    body = r.json() if ct.startswith("application/json") else r.text
    if r.status_code != ok:
        raise SystemExit(f"{m} {path} -> {r.status_code}: {body}")
    return body

if __name__ == "__main__":
    period = datetime.now().strftime("%Y-%m")
    out = req("POST", f"/gl/reclose/{period}")
    print("✅ SMOKE OK: /gl/reclose returned 200")
    print(json.dumps(out, indent=2, default=str))
