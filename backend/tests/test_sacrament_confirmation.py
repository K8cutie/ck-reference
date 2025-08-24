# backend/tests/test_sacrament_confirmation.py
from __future__ import annotations

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_confirmation_creates_income_transaction():
    # 1) Create a parishioner
    p = {
        "first_name": "Juan",
        "last_name": "Dela Cruz",
        "contact_number": "09171234567",
    }
    r = client.post("/parishioners/", json=p)
    assert r.status_code in (200, 201), r.text
    parishioner_id = r.json()["id"]

    # 2) Create a Confirmation sacrament
    payload = {
        "parishioner_id": parishioner_id,
        "date": "2025-08-08",
        "fee": 450,
        "notes": "Evening batch",
        "sacrament_type": "confirmation",
        "details": {
            "confirmand": "Juan Dela Cruz",
            "sponsor_names": ["Maria Santos", "Jose Reyes"],
            "preparation_class_batch": "2025-Q3",
        },
    }
    r = client.post("/sacraments/", json=payload)
    assert r.status_code in (200, 201), r.text
    sac_id = r.json()["id"]

    # 3) Verify an Income transaction was auto-created
    r = client.get("/transactions?limit=100")
    assert r.status_code == 200, r.text
    txs = r.json()
    # Look for the transaction linked to this sacrament
    target = [
        t
        for t in txs
        if t.get("reference_no") == f"SAC-{sac_id}" and t.get("description") == "Confirmation fee"
    ]
    assert target, f"No auto-income tx found for sacrament #{sac_id}"
    assert target[0]["category_id"] is not None
