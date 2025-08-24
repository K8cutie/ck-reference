# tests/test_smoke_endpoints.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _find_tx_by_ref(rows, ref):
    for r in rows:
        if r.get("reference_no") == ref:
            return r
    return None


def test_smoke_confirmation_crud_and_tx_sync():
    # Create a parishioner
    r = client.post(
        "/parishioners/",
        json={"first_name": "Smoke", "last_name": "Test", "contact_number": "09999999999"},
    )
    assert r.status_code in (200, 201), r.text
    pid = r.json()["id"]

    # Create a Confirmation (fee > 0 => auto Income)
    payload = {
        "parishioner_id": pid,
        "date": "2025-09-01",
        "fee": 200,
        "notes": "Smoke confirmation",
        "sacrament_type": "confirmation",
        "details": {
            "confirmand": "Juan Smoke",
            "sponsor_names": ["Sponsor A", "Sponsor B"],
            "preparation_class_batch": "2025-Q3",
        },
    }
    r = client.post("/sacraments/", json=payload)
    assert r.status_code in (200, 201), r.text
    sac = r.json()
    sac_id = sac["id"]
    ref = f"SAC-{sac_id}"

    # Transaction should exist
    r = client.get("/transactions?limit=300")
    assert r.status_code == 200
    tx = _find_tx_by_ref(r.json(), ref)
    assert tx is not None
    assert tx["amount"] == 200
    assert tx["description"] == "Confirmation fee"
    assert tx["date"] == "2025-09-01"
    assert tx["category_id"] is not None

    # Update fee & date -> transaction syncs
    r = client.patch(f"/sacraments/{sac_id}", json={"fee": 350, "date": "2025-09-05"})
    assert r.status_code == 200, r.text

    r = client.get("/transactions?limit=300")
    tx = _find_tx_by_ref(r.json(), ref)
    assert tx is not None
    assert tx["amount"] == 350
    assert tx["date"] == "2025-09-05"
    assert tx["description"] == "Confirmation fee"  # label unchanged

    # Drop fee to 0 -> transaction removed
    r = client.patch(f"/sacraments/{sac_id}", json={"fee": 0})
    assert r.status_code == 200, r.text
    r = client.get("/transactions?limit=300")
    assert _find_tx_by_ref(r.json(), ref) is None


def test_smoke_funeral_alias_and_category():
    # Create a parishioner
    r = client.post(
        "/parishioners/",
        json={"first_name": "Smoke2", "last_name": "Test", "contact_number": "08888888888"},
    )
    assert r.status_code in (200, 201), r.text
    pid = r.json()["id"]

    # Create a Funeral (alias for DEATH)
    payload = {
        "parishioner_id": pid,
        "date": "2025-10-10",
        "fee": 100,
        "notes": "Smoke funeral",
        "sacrament_type": "funeral",
        "details": {
            "deceased": "Lola Sample",
            "date_of_death": "2025-10-08",
            "burial_site": "Sample Cemetery",
        },
    }
    r = client.post("/sacraments/", json=payload)
    assert r.status_code in (200, 201), r.text
    sac = r.json()
    assert sac["sacrament_type"] == "funeral"
    sac_id = sac["id"]
    ref = f"SAC-{sac_id}"

    # Transaction description + category label should reflect "Funeral"
    r = client.get("/transactions?limit=300")
    assert r.status_code == 200
    tx = _find_tx_by_ref(r.json(), ref)
    assert tx is not None
    assert tx["description"] == "Funeral fee"
    assert tx["amount"] == 100

    # Category exists with pretty name
    r = client.get("/categories")
    assert r.status_code == 200
    cats = r.json()
    assert any(c["name"] == "Sacraments – Funeral" for c in cats)
