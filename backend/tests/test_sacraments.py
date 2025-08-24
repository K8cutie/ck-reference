from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
from app.db import SessionLocal
from app.models.transactions import Transaction  # ← plural “transactions”

client = TestClient(app)


def _count_transactions(db):
    return db.query(Transaction).count()


def test_baptism_create_and_auto_income():
    """POST a baptism, verify JSON details + auto-income transaction."""
    payload = {
        "parishioner_id": 1,  # make sure id=1 exists in your seed data
        "sacrament_type": "baptism",
        "date": str(date.today()),
        "fee": 800,
        "notes": "Infant baptism",
        "details": {
            "mother": "Maria Lopez",
            "father": "Jose Dela Cruz",
            "child_name": "Juan Dela Cruz",
            "god_parents": ["Ana Reyes", "Carlos Santos"],
        },
    }

    with SessionLocal() as db:
        before = _count_transactions(db)

    # create sacrament
    res = client.post("/sacraments/", json=payload)
    assert res.status_code == 201
    sac = res.json()
    assert sac["details"]["child_name"] == "Juan Dela Cruz"

    # auto-transaction check
    with SessionLocal() as db:
        after = _count_transactions(db)
        assert after == before + 1

        tx = db.query(Transaction).order_by(Transaction.id.desc()).first()
        assert tx.amount == Decimal("800")
        assert tx.type == "income"
        assert tx.reference_no == f"SAC-{sac['id']}"
