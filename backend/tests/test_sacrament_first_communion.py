from __future__ import annotations

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_first_communion_creates_income_transaction_and_category():
    # 1) Create a parishioner
    r = client.post(
        "/parishioners/",
        json={"first_name": "Liza", "last_name": "Cruz", "contact_number": "09170000002"},
    )
    assert r.status_code in (200, 201), r.text
    pid = r.json()["id"]

    # 2) Create a First Communion sacrament
    payload = {
        "parishioner_id": pid,
        "date": "2025-08-08",
        "fee": 600,
        "notes": "Group ceremony",
        "sacrament_type": "first_communion",
        "details": {
            "communicant": "Liza Cruz",
            "sponsor_names": ["Ninang A", "Ninong B"],
            "preparation_class_batch": "2025-Q3"
        },
    }
    r = client.post("/sacraments/", json=payload)
    assert r.status_code in (200, 201), r.text
    sac_id = r.json()["id"]

    # 3) Verify auto Income transaction exists and category present
    r = client.get("/transactions?limit=200")
    assert r.status_code == 200, r.text
    txs = r.json()
    tx = next((t for t in txs if t.get("reference_no") == f"SAC-{sac_id}"), None)
    assert tx is not None, "Auto-income transaction not found"
    assert tx["description"] == "First Communion fee"
    assert tx["category_id"] is not None

    r = client.get("/categories")
    assert r.status_code == 200
    cats = r.json()
    assert any(c["name"] == "Sacraments – First Communion" for c in cats)
