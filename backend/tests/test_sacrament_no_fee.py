from __future__ import annotations

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _make_parishioner():
    r = client.post("/parishioners/", json={
        "first_name": "Zero",
        "last_name": "Fee",
        "contact_number": "09170009999",
    })
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def test_no_transaction_when_fee_is_zero():
    pid = _make_parishioner()
    payload = {
        "parishioner_id": pid,
        "date": "2025-08-08",
        "fee": 0,
        "notes": "Should not create income",
        "sacrament_type": "baptism",
        "details": {
            "mother": "Maria Zero",
            "father": "Jose Zero",
            "child_name": "Baby Zero",
            "god_parents": ["A", "B"],
        },
    }
    r = client.post("/sacraments/", json=payload)
    assert r.status_code in (200, 201), r.text
    sac_id = r.json()["id"]

    r = client.get("/transactions?limit=300")
    assert r.status_code == 200
    txs = r.json()
    assert not any(t.get("reference_no") == f"SAC-{sac_id}" for t in txs), "Should not auto-create income for fee=0"


def test_no_transaction_when_fee_missing():
    pid = _make_parishioner()
    payload = {
        "parishioner_id": pid,
        "date": "2025-08-08",
        "notes": "Fee omitted, no income expected",
        "sacrament_type": "baptism",
        "details": {
            "mother": "Maria None",
            "father": "Jose None",
            "child_name": "Baby None",
            "god_parents": ["C", "D"],
        },
    }
    r = client.post("/sacraments/", json=payload)
    assert r.status_code in (200, 201), r.text
    sac_id = r.json()["id"]

    r = client.get("/transactions?limit=300")
    assert r.status_code == 200
    txs = r.json()
    assert not any(t.get("reference_no") == f"SAC-{sac_id}" for t in txs), "Should not auto-create income when fee is None"
