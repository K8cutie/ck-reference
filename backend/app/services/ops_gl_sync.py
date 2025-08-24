# app/services/ops_gl_sync.py
# Auto-post ops Transactions into Books (GL), honoring per-category GL mappings.

from __future__ import annotations
from datetime import date
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.transactions import Transaction  # ops layer
from app.models.gl_accounting import GLAccount, JournalEntry  # books layer
from app.models.category_gl_map import CategoryGLMap  # new mapping table

# Reuse existing GL services
from app.services.gl_accounting import (
    create_journal_entry,
    post_journal_entry,
)

# ----------------------- helpers -----------------------

def _first_active_cash(db: Session) -> Optional[GLAccount]:
    return db.execute(
        select(GLAccount)
        .where(GLAccount.is_active.is_(True), GLAccount.is_cash.is_(True))
        .order_by(GLAccount.code.asc())
    ).scalars().first()


def _first_active_by_type(db: Session, t: str) -> Optional[GLAccount]:
    return db.execute(
        select(GLAccount)
        .where(GLAccount.is_active.is_(True), GLAccount.type == t)
        .order_by(GLAccount.code.asc())
    ).scalars().first()


def _get_category_map(db: Session, category_id: Optional[int]) -> Optional[CategoryGLMap]:
    if not category_id:
        return None
    return db.execute(
        select(CategoryGLMap).where(CategoryGLMap.category_id == category_id)
    ).scalars().first()


def _already_synced(db: Session, tx_id: int) -> Optional[int]:
    """Return existing JE id if this tx is already synced; else None."""
    je_id = db.execute(
        select(JournalEntry.id).where(
            JournalEntry.source_module == "ops",
            JournalEntry.source_id == f"tx:{tx_id}",
        )
    ).scalar()
    return int(je_id) if je_id else None


def _resolve_accounts_for_tx(db: Session, tx: Transaction) -> Tuple[Optional[int], Optional[int]]:
    """
    Decide debit and credit account IDs for a transaction, using:
      1) CategoryGLMap (if present for tx.category_id)
      2) Fallback defaults: cash + income/expense GLs
    Rules:
      - INCOME:   Dr Cash / Cr Income
      - EXPENSE:  Dr Expense / Cr Cash
    """
    tx_type = (getattr(tx.type, "value", None) or str(tx.type) or "").lower()

    # Fallbacks
    cash_acc = _first_active_cash(db)
    income_acc = _first_active_by_type(db, "income")
    expense_acc = _first_active_by_type(db, "expense")

    # Mapping (may be partial)
    cmap = _get_category_map(db, getattr(tx, "category_id", None))

    if tx_type == "income":
        dr = (cmap.debit_account_id if (cmap and cmap.debit_account_id) else (cash_acc.id if cash_acc else None))
        cr = (cmap.credit_account_id if (cmap and cmap.credit_account_id) else (income_acc.id if income_acc else None))
        return dr, cr

    if tx_type == "expense":
        dr = (cmap.debit_account_id if (cmap and cmap.debit_account_id) else (expense_acc.id if expense_acc else None))
        cr = (cmap.credit_account_id if (cmap and cmap.credit_account_id) else (cash_acc.id if cash_acc else None))
        return dr, cr

    # Unknown type -> skip auto-post
    return None, None


# ----------------------- main entry -----------------------

def ensure_tx_synced_to_gl(db: Session, tx: Transaction) -> Optional[int]:
    """
    Ensure an ops Transaction has a posted Journal Entry in Books.
    - Idempotent via (source_module="ops", source_id=f"tx:{id}")
    - Honors CategoryGLMap if present for tx.category_id
    - Falls back to first active cash/income/expense accounts when needed
    - Skips voided or non-positive amounts
    Returns the JE id if created or found; otherwise None.
    """
    if not isinstance(tx, Transaction) or tx.id is None:
        return None
    if getattr(tx, "voided", False):
        return None

    # Idempotency
    existing = _already_synced(db, tx.id)
    if existing:
        return existing

    amount = float(getattr(tx, "amount", 0) or 0)
    if amount <= 0:
        return None

    debit_acc_id, credit_acc_id = _resolve_accounts_for_tx(db, tx)
    if not debit_acc_id or not credit_acc_id:
        # Not enough info to form a balanced entry; skip silently
        return None

    payload = {
        "entry_date": tx.date if isinstance(tx.date, date) else date.today(),
        "memo": (tx.description or None),
        "currency_code": "PHP",
        "reference_no": (tx.reference_no or f"TX-{tx.id}"),
        "source_module": "ops",
        "source_id": f"tx:{tx.id}",
        "lines": [
            {
                "account_id": int(debit_acc_id),
                "line_no": 1,
                "description": "Auto-post from ops",
                "debit": amount,
                "credit": 0.0,
            },
            {
                "account_id": int(credit_acc_id),
                "line_no": 2,
                "description": "Auto-post from ops",
                "debit": 0.0,
                "credit": amount,
            },
        ],
    }

    # IMPORTANT: create_journal_entry requires keyword-only args after db
    je = create_journal_entry(db, **payload)
    post_journal_entry(db, je.id)
    return int(je.id)
