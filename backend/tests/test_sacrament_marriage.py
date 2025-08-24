from __future__ import annotations

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_marriage_creates_income_transaction_and_category():
    # 1) Create a parishioner
    r = client.post(
        "/parishioners/",
        json={"first_name": "Marco", "last_name": "Reyes", "contact_number": "09170000001"},
    )
    assert r.status_code in (200, 201), r.text
    pid = r.json()["id"]

    # 2) Create a Marriage sacrament
    payload = {
        "parishioner_id": pid,
        "date": "2025-08-08",
        "fee": 1200,
        "notes": "Beach wedding",
        "sacrament_type": "marriage",
        "details": {
            "bride": "Ana Santos",
            "groom": "Marco Reyes",
            "place_of_marriage": "St. John Parish",
            "witnesses": ["Tita A", "Tito B"],
        },
    }
    r = client.post("/sacraments/", json=payload)
    assert r.status_code in (200, 201), r.text
    sac_id = r.json()["id"]

    # 3) Verify auto Income transaction exists and category present
    r = client.get("/transactions?limit=100")
    assert r.status_code == 200, r.text
    txs = r.json()
    tx = next((t for t in txs if t.get("reference_no") == f"SAC-{sac_id}"), None)
    assert tx is not None, "Auto-income transaction not found"
    assert tx["description"] == "Marriage fee"
    assert tx["category_id"] is not None

    r = client.get("/categories")
    assert r.status_code == 200
    cats = r.json()
    assert any(c["name"] == "Sacraments – Marriage" for c in cats)
