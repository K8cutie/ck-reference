# scripts/smoke_sigma.py
# Quick end-to-end smoke test for Six Sigma endpoints.
# Requires: pip install requests

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import requests


BASE = os.getenv("CK_API", "http://127.0.0.1:8000")
TZ = timezone(timedelta(hours=8))  # Asia/Manila offset without needing zoneinfo


def iso(dt: datetime) -> str:
    return dt.isoformat()


def must_ok(r: requests.Response, code: int = 200):
    try:
        r.raise_for_status()
    except Exception as e:
        print("✗ HTTP error:", e)
        print("→ URL:", r.request.method, r.request.url)
        if r.content:
            print("→ Body:", r.text[:1000])
        sys.exit(1)
    if r.status_code != code:
        print(f"✗ Expected {code} got {r.status_code} for {r.request.method} {r.request.url}")
        print("→ Body:", r.text[:1000])
        sys.exit(1)


def approx(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) <= tol


def main():
    print(f"→ Using API {BASE}")

    # Unique process so repeated runs don't collide
    process = f"SMOKE-{uuid.uuid4().hex[:8]}"
    ctq = "WaitTime"

    # Window: tomorrow 08:00–10:00 (+08:00)
    day0 = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    ps = day0 + timedelta(days=1, hours=8)
    pe = ps + timedelta(hours=2)

    # Query range a bit wider to ensure inclusion
    qstart = ps - timedelta(days=1)
    qend = pe + timedelta(days=1)

    # 1) Create a log (100 units, 3 opp/unit, 12 defects)
    payload_log = {
        "process": process,
        "ctq": ctq,
        "period_start": iso(ps),
        "period_end": iso(pe),
        "units": 100,
        "opportunities_per_unit": 3,
        "defects": 12,
        "notes": "sigma smoke test",
    }
    r = requests.post(f"{BASE}/sigma/logs", json=payload_log)
    must_ok(r, 201)
    data_log = r.json()
    assert data_log["process"] == process
    assert data_log["defects"] == 12
    print("✓ Created sigma log")

    # 2) Add categorized defects that sum to 12
    payload_def = {
        "process": process,
        "ctq": ctq,
        "period_start": iso(ps),
        "period_end": iso(pe),
        "items": [
            {"category": "Door Jam", "count": 6},
            {"category": "Late Start", "count": 4},
            {"category": "Seat Mapping", "count": 2},
        ],
        "notes": "sigma smoke test defects",
    }
    r = requests.post(f"{BASE}/sigma/defects", json=payload_def)
    must_ok(r, 201)
    items = r.json()
    assert len(items) == 3
    print("✓ Inserted defect categories")

    # 3) Summary should reflect our exact numbers
    r = requests.get(
        f"{BASE}/sigma/summary",
        params={"process": process, "start": iso(qstart), "end": iso(qend)},
    )
    must_ok(r)
    summ = r.json()
    assert summ["units"] == 100
    assert summ["opportunities"] == 300
    assert summ["defects"] == 12
    assert approx(float(summ["dpu"]), 12 / 300)
    # dpmo may be rounded server-side; allow small tolerance
    assert abs(float(summ["dpmo"]) - 40000.0) < 0.1
    print("✓ Summary metrics ok")

    # 4) p-chart JSON
    r = requests.get(
        f"{BASE}/sigma/control-chart",
        params={"process": process, "start": iso(qstart), "end": iso(qend), "tz": "Asia/Manila"},
    )
    must_ok(r)
    chart = r.json()
    assert chart["process"] == process
    assert approx(float(chart["p_bar"]), 12 / 300)
    assert len(chart["points"]) >= 1
    pt = chart["points"][0]
    assert pt["opportunities"] == 300
    assert pt["defects"] == 12
    assert approx(float(pt["p_hat"]), 12 / 300)
    print("✓ Control chart JSON ok")

    # 5) Pareto JSON (limit=2 -> third bucket collapsed to 'Other')
    r = requests.get(
        f"{BASE}/sigma/pareto",
        params={
            "process": process,
            "ctq": ctq,
            "start": iso(qstart),
            "end": iso(qend),
            "limit": 2,
        },
    )
    must_ok(r)
    pareto = r.json()
    assert pareto["total"] == 12
    cats = [row["category"] for row in pareto["items"]]
    assert cats[:2] == ["Door Jam", "Late Start"]
    assert cats[-1] == "Other"
    print("✓ Pareto JSON ok")

    # 6) Pareto CSV
    r = requests.get(
        f"{BASE}/sigma/pareto.csv",
        params={"process": process, "ctq": ctq, "start": iso(qstart), "end": iso(qend), "limit": 2},
    )
    must_ok(r)
    ctype = r.headers.get("content-type", "").lower()
    assert "text/csv" in ctype or "application/octet-stream" in ctype
    text = r.text.splitlines()
    assert text[0].startswith("category,count")
    assert any("Door Jam" in line for line in text[1:])
    print("✓ Pareto CSV ok")

    # 7) Charts as PNGs
    r = requests.get(
        f"{BASE}/sigma/control-chart.png",
        params={"process": process, "start": iso(qstart), "end": iso(qend), "tz": "Asia/Manila"},
    )
    must_ok(r)
    assert "image/png" in r.headers.get("content-type", "").lower()
    assert len(r.content) > 1000
    print("✓ Control chart PNG ok")

    r = requests.get(
        f"{BASE}/sigma/pareto.png",
        params={"process": process, "ctq": ctq, "start": iso(qstart), "end": iso(qend), "limit": 2},
    )
    must_ok(r)
    assert "image/png" in r.headers.get("content-type", "").lower()
    assert len(r.content) > 1000
    print("✓ Pareto PNG ok")

    print("\nALL SIGMA SMOKE TESTS PASSED ✅")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
