# tests/test_sigma_integration.py
# End-to-end test for Six Sigma endpoints.

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE = os.getenv("CK_API", "http://127.0.0.1:8000")
TZ = timezone(timedelta(hours=8))  # Asia/Manila offset


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _approx(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) <= tol


def _service_up() -> bool:
    try:
        r = requests.get(f"{BASE}/openapi.json", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


skip_if_down = pytest.mark.skipif(not _service_up(), reason="API not reachable")


@skip_if_down
def test_sigma_e2e():
    # unique per-run process name to avoid collisions
    process = f"SMOKE-{uuid.uuid4().hex[:8]}"
    ctq = "WaitTime"

    # window: tomorrow 08:00–10:00 (+08:00)
    day0 = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    ps = day0 + timedelta(days=1, hours=8)
    pe = ps + timedelta(hours=2)

    # query range a bit wider to ensure inclusion
    qstart = ps - timedelta(days=1)
    qend = pe + timedelta(days=1)

    # 1) create a log (100 units, 3 opp/unit, 12 defects)
    payload_log = {
        "process": process,
        "ctq": ctq,
        "period_start": _iso(ps),
        "period_end": _iso(pe),
        "units": 100,
        "opportunities_per_unit": 3,
        "defects": 12,
        "notes": "sigma pytest",
    }
    r = requests.post(f"{BASE}/sigma/logs", json=payload_log, timeout=10)
    assert r.status_code == 201, r.text
    data_log = r.json()
    assert data_log["process"] == process
    assert data_log["defects"] == 12

    # 2) add categorized defects summing to 12
    payload_def = {
        "process": process,
        "ctq": ctq,
        "period_start": _iso(ps),
        "period_end": _iso(pe),
        "items": [
            {"category": "Door Jam", "count": 6},
            {"category": "Late Start", "count": 4},
            {"category": "Seat Mapping", "count": 2},
        ],
        "notes": "sigma pytest defects",
    }
    r = requests.post(f"{BASE}/sigma/defects", json=payload_def, timeout=10)
    assert r.status_code == 201, r.text
    items = r.json()
    assert isinstance(items, list) and len(items) == 3

    # 3) summary reflects numbers
    r = requests.get(
        f"{BASE}/sigma/summary",
        params={"process": process, "start": _iso(qstart), "end": _iso(qend)},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    summ = r.json()
    assert summ["units"] == 100
    assert summ["opportunities"] == 300
    assert summ["defects"] == 12

    # DPU here is defects per UNIT (standard): 12 / 100 = 0.12
    assert _approx(float(summ["dpu"]), 12 / 100)

    # DPMO should align with defects per opportunity * 1e6: (12 / 300) * 1e6 = 40000
    assert abs(float(summ["dpmo"]) - 40000.0) < 0.1

    # 4) p-chart JSON
    r = requests.get(
        f"{BASE}/sigma/control-chart",
        params={"process": process, "start": _iso(qstart), "end": _iso(qend), "tz": "Asia/Manila"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    chart = r.json()
    assert chart["process"] == process
    assert _approx(float(chart["p_bar"]), 12 / 300)
    assert len(chart["points"]) >= 1
    pt = chart["points"][0]
    assert pt["opportunities"] == 300
    assert pt["defects"] == 12
    assert _approx(float(pt["p_hat"]), 12 / 300)

    # 5) Pareto JSON (limit=2 -> third bucket collapses to 'Other')
    r = requests.get(
        f"{BASE}/sigma/pareto",
        params={"process": process, "ctq": ctq, "start": _iso(qstart), "end": _iso(qend), "limit": 2},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    pareto = r.json()
    assert pareto["total"] == 12
    names = [row["category"] for row in pareto["items"]]
    assert names[:2] == ["Door Jam", "Late Start"]
    assert names[-1] == "Other"

    # 6) Pareto CSV
    r = requests.get(
        f"{BASE}/sigma/pareto.csv",
        params={"process": process, "ctq": ctq, "start": _iso(qstart), "end": _iso(qend), "limit": 2},
        timeout=10,
    )
    assert r.status_code == 200
    ctype = r.headers.get("content-type", "").lower()
    assert "text/csv" in ctype or "application/octet-stream" in ctype
    lines = r.text.splitlines()
    assert lines[0].startswith("category,count")
    assert any("Door Jam" in line for line in lines[1:])

    # 7) PNG charts
    r = requests.get(
        f"{BASE}/sigma/control-chart.png",
        params={"process": process, "start": _iso(qstart), "end": _iso(qend), "tz": "Asia/Manila"},
        timeout=10,
    )
    assert r.status_code == 200
    assert "image/png" in r.headers.get("content-type", "").lower()
    assert len(r.content) > 1000

    r = requests.get(
        f"{BASE}/sigma/pareto.png",
        params={"process": process, "ctq": ctq, "start": _iso(qstart), "end": _iso(qend), "limit": 2},
        timeout=10,
    )
    assert r.status_code == 200
    assert "image/png" in r.headers.get("content-type", "").lower()
    assert len(r.content) > 1000
