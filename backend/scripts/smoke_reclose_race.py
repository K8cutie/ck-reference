# backend/scripts/smoke_reclose_race.py
import sys, json, time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

BASE = "http://127.0.0.1:8000"

def call_reclose(period):
    try:
        r = requests.post(f"{BASE}/gl/reclose/{period}", timeout=60)
        ct = r.headers.get("content-type","")
        body = r.json() if ct.startswith("application/json") else r.text
        return r.status_code, body
    except Exception as e:
        return -1, str(e)

def main():
    period = datetime.now().strftime("%Y-%m")
    # small sync barrier
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(call_reclose, period) for _ in range(2)]
        results = [f.result() for f in as_completed(futs)]
    ok = sum(1 for s, _ in results if s == 200)
    busy = sum(1 for s, b in results if s == 400 and isinstance(b, dict) and "busy" in str(b.get("detail","")).lower())
    print("Results:", results)
    if ok == 1 and busy == 1:
        print("✅ RACE SMOKE OK: one success, one busy")
        return 0
    else:
        print("❌ RACE SMOKE FAIL")
        return 1

if __name__ == "__main__":
    sys.exit(main())
