# scripts/test_autopost_income.py
# Creates a minimal INCOME Transaction for category_id=2 (Baptism)
# then calls ensure_tx_synced_to_gl to create & post a Journal Entry.
#
# Run from C:\ckchurch1\backend with venv active:
#   python scripts/test_autopost_income.py

from __future__ import annotations

# --- Ensure project root is importable as "app" ---
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# --- Dynamically import ALL submodules under app.models so string relationships resolve ---
def _import_all_models() -> None:
    import importlib
    import pkgutil
    import app.models as models_pkg  # base package

    # Import the base package first
    importlib.import_module(models_pkg.__name__)

    # Recursively import all subpackages/submodules (e.g., app.models.sacraments)
    for _finder, modname, _ispkg in pkgutil.walk_packages(
        models_pkg.__path__, prefix=models_pkg.__name__ + "."
    ):
        try:
            importlib.import_module(modname)
        except Exception:
            # If any model module raises import-time errors, we skip;
            # we only need classes to be registered for relationship resolution.
            pass

_import_all_models()

from datetime import date
from decimal import Decimal
from sqlalchemy import select

from app.db import SessionLocal
from app.models.transactions import Transaction, TransactionType
from app.services.ops_gl_sync import ensure_tx_synced_to_gl
from app.models.gl_accounting import JournalEntry, JournalLine


def _coerce_income_enum() -> TransactionType:
    # Handle either TransactionType.INCOME or TransactionType.income
    if hasattr(TransactionType, "INCOME"):
        return getattr(TransactionType, "INCOME")
    if hasattr(TransactionType, "income"):
        return getattr(TransactionType, "income")
    # Fallback: try value by string name if enum uses different casing
    for v in TransactionType:
        if str(getattr(v, "value", v)).lower() == "income":
            return v
    raise RuntimeError("Cannot resolve TransactionType for income")


def main():
    with SessionLocal() as db:
        income_enum = _coerce_income_enum()

        # 1) Create a minimal income Transaction for category_id=2 (Baptism)
        tx = Transaction(
            date=date.today(),
            description="Test Baptism income (auto-post)",
            amount=Decimal("1500.00"),
            type=income_enum,
            category_id=2,  # Baptism
            reference_no=None,
        )
        db.add(tx)
        db.commit()         # must commit so tx.id exists & persists
        db.refresh(tx)

        print(f"✅ Created Transaction id={tx.id}, amount={tx.amount}, category_id={tx.category_id}")

        # 2) Ensure it is synced to GL (uses your Category → GL mapping)
        je_id = ensure_tx_synced_to_gl(db, tx)
        db.commit()

        if not je_id:
            print("⚠️ No Journal Entry created (missing mapped/fallback accounts or amount <= 0).")
            return

        # 3) Fetch the JE and print lines
        je = db.get(JournalEntry, je_id)
        if not je:
            print(f"⚠️ JournalEntry id={je_id} not found after posting.")
            return

        print(f"✅ Posted JournalEntry id={je.id}, entry_date={je.entry_date}, reference={je.reference_no}")

        # NOTE: column is 'entry_id' (not journal_entry_id)
        lines = db.execute(
            select(JournalLine)
            .where(JournalLine.entry_id == je.id)
            .order_by(JournalLine.line_no.asc())
        ).scalars().all()

        for ln in lines:
            print(f"   • line {ln.line_no}: acct={ln.account_id}  Dr {ln.debit}  Cr {ln.credit}")

        print("Done.")


if __name__ == "__main__":
    main()
