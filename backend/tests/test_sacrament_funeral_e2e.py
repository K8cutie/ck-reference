from __future__ import annotations

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_funeral_alias_e2e():
    # 1) Create a parishioner
    r = client.post(
        "/parishioners/",
        json={"first_name": "Jose", "last_name": "Rizal", "contact_number": "09170000003"},
    )
    assert r.status_code in (200, 201), r.text
    pid = r.json()["id"]

    # 2) Create a Funeral sacrament (alias for DEATH)
    payload = {
        "parishioner_id": pid,
        "date": "2025-08-08",
        "fee": 900,
        "notes": "Evening service",
        "sacrament_type": "funeral",
        "details": {
            "deceased": "Lola Maria",
            "date_of_death": "2025-08-06",
            "burial_site": "Family Home Cemetery"
        },
    }

    r = client.post("/sacraments/", json=payload)
    assert r.status_code in (200, 201), r.text
    body = r.json()
    sac_id = body["id"]

    # API should return the alias string, not DEATH
    assert body["sacrament_type"] == "funeral"

    # 3) Transaction creation & description/Category label
    r = client.get("/transactions?limit=300")
    assert r.status_code == 200, r.text
    txs = r.json()
    tx = next((t for t in txs if t.get("reference_no") == f"SAC-{sac_id}"), None)
    assert tx is not None, "Auto-income transaction not found"
    assert tx["description"] == "Funeral fee"  # not "Death fee"
    assert tx["category_id"] is not None

    # 4) Category name is “Sacraments – Funeral”
    r = client.get("/categories")
    assert r.status_code == 200
    cats = r.json()
    assert any(c["name"] == "Sacraments – Funeral" for c in cats)
