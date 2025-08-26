from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from app.models.gl_accounting import (
    GLAccount,
    JournalEntry,
    JournalLine,
    AuditLog,
)
from app.services.gl.locks import _is_period_locked

# --- tiny local helpers to avoid circular imports ---

def _get_gl_account(db: Session, account_id: int) -> Optional[GLAccount]:
    return db.get(GLAccount, account_id)

def _log(
    db: Session,
    entity_type: str,
    entity_id: str,
    action: str,
    details: dict | None = None,
) -> None:
    try:
        db.add(
            AuditLog(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                details=None if details is None else str(details),
                created_at=datetime.utcnow(),
            )
        )
        db.flush()
    except Exception:
        db.rollback()

# --- public API ---

def create_journal_entry(
    db: Session,
    *,
    entry_date: date,
    memo: Optional[str],
    currency_code: str,
    reference_no: Optional[str],
    source_module: Optional[str],
    source_id: Optional[str],
    lines: Iterable[dict],
    created_by_user_id: Optional[int] = None,
) -> JournalEntry:
    line_objs: List[JournalLine] = []
    total_debits = Decimal("0.00")
    total_credits = Decimal("0.00")
    next_line_no = 1

    for ln in lines:
        acct_id = int(ln["account_id"])
        acct = _get_gl_account(db, acct_id)
        if not acct:
            raise ValueError(f"GL account not found: {acct_id}")

        debit = Decimal(str(ln.get("debit", "0") or "0"))
        credit = Decimal(str(ln.get("credit", "0") or "0"))
        if not ((debit > 0 and credit == 0) or (credit > 0 and debit == 0)):
            raise ValueError("Each line must have either a positive debit or a positive credit, not both or neither.")

        total_debits += debit
        total_credits += credit

        line_objs.append(
            JournalLine(
                account_id=acct.id,
                description=(ln.get("description") or None),
                debit=debit,
                credit=credit,
                line_no=int(ln.get("line_no") or next_line_no),
            )
        )
        next_line_no += 1

    if (total_debits - total_credits).quantize(Decimal("0.01")) != Decimal("0.00"):
        raise ValueError("Entry not balanced (total debits != total credits).")

    je = JournalEntry(
        entry_date=entry_date,
        memo=memo,
        currency_code=currency_code or "PHP",
        reference_no=reference_no,
        source_module=source_module,
        source_id=source_id,
        created_by_user_id=created_by_user_id,
        is_locked=False,
    )
    db.add(je)
    db.flush()

    for ln in line_objs:
        ln.entry_id = je.id
        db.add(ln)

    _log(db, "journal_entry", str(je.id), "create", {"entry_id": je.id})
    db.commit()
    db.refresh(je)
    return je


def post_journal_entry(
    db: Session,
    je_id: int,
    *,
    posted_by_user_id: Optional[int] = None,
) -> JournalEntry:
    je = db.get(JournalEntry, je_id)
    if not je:
        raise ValueError("Journal entry not found.")

    if je.is_locked:
        return je

    if _is_period_locked(db, je.entry_date):
        y_m = je.entry_date.strftime("%Y-%m")
        raise ValueError(f"Cannot post: period {y_m} is locked.")

    total_debits = sum((ln.debit or 0) for ln in je.lines)
    total_credits = sum((ln.credit or 0) for ln in je.lines)
    if round(float(total_debits) - float(total_credits), 2) != 0.0:
        raise ValueError("Cannot post unbalanced journal entry.")

    now = datetime.utcnow()
    je.posted_at = now
    je.posted_by_user_id = posted_by_user_id
    je.is_locked = True
    je.locked_at = now

    _log(db, "journal_entry", str(je.id), "post", {"entry_id": je.id})
    db.commit()
    db.refresh(je)
    return je


def unpost_journal_entry(
    db: Session,
    je_id: int,
    *,
    unposted_by_user_id: Optional[int] = None,
) -> JournalEntry:
    je = db.get(JournalEntry, je_id)
    if not je:
        raise ValueError("Journal entry not found.")

    if not je.is_locked:
        return je

    if _is_period_locked(db, je.entry_date):
        y_m = je.entry_date.strftime("%Y-%m")
        raise ValueError(f"Cannot unpost: period {y_m} is locked.")

    je.posted_at = None
    je.posted_by_user_id = None
    je.is_locked = False
    je.locked_at = None

    _log(db, "journal_entry", str(je.id), "unpost", {"entry_id": je.id})
    db.commit()
    db.refresh(je)
    return je


def reverse_journal_entry(
    db: Session,
    je_id: int,
    *,
    as_of: Optional[date] = None,
    created_by_user_id: Optional[int] = None,
) -> JournalEntry:
    src = db.get(JournalEntry, je_id)
    if not src:
        raise ValueError("Journal entry not found.")
    if not src.is_locked:
        raise ValueError("Cannot reverse a draft journal entry.")

    rev_date = as_of or src.entry_date
    if _is_period_locked(db, rev_date):
        y_m = rev_date.strftime("%Y-%m")
        raise ValueError(f"Cannot create reversal in locked period {y_m}.")

    # swap debit/credit
    lines: List[dict] = []
    for ln in src.lines:
        lines.append(
            {
                "account_id": ln.account_id,
                "description": f"Reversal of JE {src.entry_no}",
                "debit": float(ln.credit or 0),
                "credit": float(ln.debit or 0),
            }
        )

    ref_base = src.reference_no or f"JE-{src.entry_no}"
    ref_rev = f"{ref_base}-REV"

    rev = create_journal_entry(
        db,
        entry_date=rev_date,
        memo=(src.memo or "") + " (reversal)",
        currency_code=src.currency_code or "PHP",
        reference_no=ref_rev,
        source_module="reversal",
        source_id=str(src.id),
        lines=lines,
        created_by_user_id=created_by_user_id,
    )
    return post_journal_entry(db, rev.id, posted_by_user_id=created_by_user_id)
