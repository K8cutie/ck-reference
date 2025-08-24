from __future__ import annotations

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _find_tx_by_ref(txs, ref):
    return next((t for t in txs if t.get("reference_no") == ref), None)


def test_sacrament_update_keeps_transaction_in_sync():
    # 1) Create a parishioner
    r = client.post(
        "/parishioners/",
        json={"first_name": "Ana", "last_name": "Santos", "contact_number": "09171234567"},
    )
    assert r.status_code in (200, 201), r.text
    pid = r.json()["id"]

    # 2) Create a Baptism sacrament (fee > 0 => auto-create income tx)
    payload = {
        "parishioner_id": pid,
        "date": "2025-08-10",
        "fee": 500,
        "notes": "Morning batch",
        "sacrament_type": "baptism",
        "details": {
            "child_name": "Ana Jr.",
            "mother": "Ana Santos",
            "father": "Juan Santos",
            "god_parents": ["Maria Lopez", "Jose Cruz"],
        },
    }
    r = client.post("/sacraments/", json=payload)
    assert r.status_code in (200, 201), r.text
    sac = r.json()
    sac_id = sac["id"]
    ref = f"SAC-{sac_id}"

    # Transaction should exist and match initial values
    r = client.get("/transactions?limit=300")
    assert r.status_code == 200, r.text
    tx = _find_tx_by_ref(r.json(), ref)
    assert tx is not None, "Auto-income transaction not created"
    assert tx["amount"] == 500
    assert tx["description"] == "Baptism fee"
    assert tx["date"] == "2025-08-10"
    assert tx["category_id"] is not None

    # 3) Update fee and date -> transaction should update in place
    r = client.patch(f"/sacraments/{sac_id}", json={"fee": 800, "date": "2025-08-11"})
    assert r.status_code == 200, r.text

    r = client.get("/transactions?limit=300")
    assert r.status_code == 200
    tx = _find_tx_by_ref(r.json(), ref)
    assert tx is not None
    assert tx["amount"] == 800
    assert tx["date"] == "2025-08-11"
    assert tx["description"] == "Baptism fee"  # still baptism

    # 4) Change type to funeral (alias of DEATH) with required details
    r = client.patch(
        f"/sacraments/{sac_id}",
        json={
            "sacrament_type": "funeral",
            "details": {
                "deceased": "Lola Maria",
                "date_of_death": "2025-08-09",
                "burial_site": "Family Home Cemetery",
            },
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sacrament_type"] == "funeral"

    # Transaction should now reflect the new label/category
    r = client.get("/transactions?limit=300")
    assert r.status_code == 200
    tx = _find_tx_by_ref(r.json(), ref)
    assert tx is not None
    assert tx["amount"] == 800  # unchanged
    assert tx["description"] == "Funeral fee"  # label updated

    # Category should exist with the pretty name
    r = client.get("/categories")
    assert r.status_code == 200
    cats = r.json()
    assert any(c["name"] == "Sacraments – Funeral" for c in cats)

    # 5) Set fee to 0 -> transaction should be deleted
    r = client.patch(f"/sacraments/{sac_id}", json={"fee": 0})
    assert r.status_code == 200, r.text

    r = client.get("/transactions?limit=300")
    assert r.status_code == 200
    tx = _find_tx_by_ref(r.json(), ref)
    assert tx is None, "Transaction should be removed when fee becomes 0"
