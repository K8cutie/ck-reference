# backend/tests/test_sacrament_baptism.py
from __future__ import annotations

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_baptism_creates_income_transaction_and_category():
    # 1) Create a parishioner
    r = client.post(
        "/parishioners/",
        json={
            "first_name": "Ana",
            "last_name": "Santos",
            "contact_number": "09170000000",
        },
    )
    assert r.status_code in (200, 201), r.text
    pid = r.json()["id"]

    # 2) Create a Baptism sacrament
    payload = {
        "parishioner_id": pid,
        "date": "2025-08-08",
        "fee": 800,
        "notes": "Morning batch",
        "sacrament_type": "baptism",
        "details": {
            "mother": "Maria Santos",
            "father": "Jose Santos",
            "child_name": "Baby Santos",
            "god_parents": ["Tita A", "Tito B"],
        },
    }
    r = client.post("/sacraments/", json=payload)
    assert r.status_code in (200, 201), r.text
    sac_id = r.json()["id"]

    # 3) Verify auto Income transaction exists
    r = client.get("/transactions?limit=100")
    assert r.status_code == 200, r.text
    txs = r.json()
    tx = next((t for t in txs if t.get("reference_no") == f"SAC-{sac_id}"), None)
    assert tx is not None, "Auto-income transaction not found"
    assert tx["description"] == "Baptism fee"
    assert tx["category_id"] is not None

    # (Optional) quick check that the category list contains "Sacraments – Baptism"
    r = client.get("/categories")
    assert r.status_code == 200
    cats = r.json()
    assert any(c["name"] == "Sacraments – Baptism" for c in cats)
