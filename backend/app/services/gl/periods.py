from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select, text, func
from sqlalchemy.orm import Session

from app.models.gl_accounting import JournalEntry
from app.services.gl.locks import _is_period_locked, _set_period_lock
from app.services.gl.journal import (
    create_journal_entry,
    post_journal_entry,
    reverse_journal_entry,
)

# ----------------------------
# Advisory lock helpers (per-month)
# ----------------------------

def _period_lock_key(year: int, month: int) -> int:
    """
    Build a small integer key for advisory locks, unique per YYYY-MM.
    Example: 2025-08 -> 202508
    """
    return year * 100 + month  # fits in 32-bit signed; ok for our purposes

def _try_lock_month(db: Session, year: int, month: int) -> bool:
    k = _period_lock_key(year, month)
    # Returns True if lock acquired, False if another session holds it
    got = db.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": k}).scalar()
    return bool(got)

def _unlock_month(db: Session, year: int, month: int) -> None:
    k = _period_lock_key(year, month)
    # Always attempt unlock; no-op if not held
    db.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": k})

def _has_posted_reversal_for(db: Session, closing_id: int) -> bool:
    """True if a posted reversal exists for the given closing JE id."""
    count = db.execute(
        select(func.count()).select_from(JournalEntry).where(
            JournalEntry.source_module == "reversal",
            JournalEntry.source_id == str(closing_id),
            JournalEntry.is_locked.is_(True),
        )
    ).scalar()
    return bool(count and int(count) > 0)

# ----------------------------
# Close / Reopen / Reclose
# ----------------------------

def close_period(
    db: Session,
    year: int,
    month: int,
    *,
    equity_account_id: int,
    note: Optional[str] = None,
    created_by_user_id: Optional[int] = None,
) -> JournalEntry:
    """
    Close Income/Expense into Equity for (year, month).
    Creates a posted JE dated last day of month with ref CLOSE-YYYYMM, then locks the period.
    Allows reclose only if every prior closing has a posted reversal keyed by source_id=<closing.id>.
    Uses a per-month advisory lock to prevent concurrent closes.
    """
    if not _try_lock_month(db, year, month):
        raise ValueError(f"Period {year}-{month:02d} is busy; try again shortly.")

    try:
        first = date(year, month, 1)
        last = date(year, month, calendar.monthrange(year, month)[1])

        if _is_period_locked(db, first):
            y_m = first.strftime("%Y-%m")
            raise ValueError(f"Cannot close: period {y_m} is locked.")

        ref = f"CLOSE-{year:04d}{month:02d}"
        closing_ids: List[int] = db.execute(
            select(JournalEntry.id).where(
                JournalEntry.reference_no == ref,
                JournalEntry.is_locked.is_(True),
            )
        ).scalars().all()
        if closing_ids:
            unresolved = [cid for cid in closing_ids if not _has_posted_reversal_for(db, cid)]
            if unresolved:
                raise ValueError(f"Already closed for {year}-{month:02d}.")

        # Aggregate posted month activity
        sql = text(
            """
            SELECT a.id AS account_id, a.type AS acct_type, a.code AS code, a.name AS name,
                   COALESCE(SUM(l.debit),0) AS dr, COALESCE(SUM(l.credit),0) AS cr
            FROM journal_lines l
            JOIN journal_entries je ON je.id = l.entry_id
            JOIN gl_accounts a ON a.id = l.account_id
            WHERE je.is_locked = TRUE
              AND je.entry_date >= :first AND je.entry_date <= :last
            GROUP BY a.id, a.type, a.code, a.name
            """
        )
        rows = db.execute(sql, {"first": first, "last": last}).mappings().all()

        income_total = Decimal("0.00")
        expense_total = Decimal("0.00")
        lines: List[dict] = []

        for r in rows:
            t = (r["acct_type"] or "").lower()
            dr = Decimal(str(r["dr"] or 0))
            cr = Decimal(str(r["cr"] or 0))
            if t == "income":
                net_credit = cr - dr
                if net_credit > 0:
                    lines.append({"account_id": int(r["account_id"]), "description": f"Close income {r['code']}", "debit": float(net_credit), "credit": 0.0})
                    income_total += net_credit
            elif t == "expense":
                net_debit = dr - cr
                if net_debit > 0:
                    lines.append({"account_id": int(r["account_id"]), "description": f"Close expense {r['code']}", "debit": 0.0, "credit": float(net_debit)})
                    expense_total += net_debit

        if not lines and income_total == 0 and expense_total == 0:
            raise ValueError(f"Nothing to close for {year}-{month:02d}.")

        equity_amt = income_total - expense_total
        if equity_amt > 0:
            lines.append({"account_id": equity_account_id, "description": f"Close {year}-{month:02d} Net Income", "debit": 0.0, "credit": float(equity_amt)})
        elif equity_amt < 0:
            lines.append({"account_id": equity_account_id, "description": f"Close {year}-{month:02d} Net Loss", "debit": float(-equity_amt), "credit": 0.0})

        je = create_journal_entry(
            db,
            entry_date=last,
            memo=f"Closing Entry {year}-{month:02d}",
            currency_code="PHP",
            reference_no=ref,
            source_module="closing",
            source_id=ref,
            lines=lines,
            created_by_user_id=created_by_user_id,
        )
        je = post_journal_entry(db, je.id, posted_by_user_id=created_by_user_id)

        _set_period_lock(db, first, True, note or "closed")
        return je
    finally:
        _unlock_month(db, year, month)

def reopen_period(
    db: Session,
    year: int,
    month: int,
    *,
    note: Optional[str] = None,
) -> dict:
    """Reopen a previously locked period (does NOT reverse closing entries)."""
    first = date(year, month, 1)
    _set_period_lock(db, first, False, note or "reopened")
    return {"period_month": first.isoformat(), "is_locked": False, "note": note or "reopened"}

def reclose_period(
    db: Session,
    year: int,
    month: int,
    *,
    equity_account_id: int,
    note: Optional[str] = None,
    created_by_user_id: Optional[int] = None,
) -> JournalEntry:
    """
    Re-close a month after new postings following a reopen:
      1) acquire per-month advisory lock (busy -> fail fast)
      2) reopen (idempotent)
      3) ensure every posted CLOSE-YYYYMM has a posted reversal keyed by source_id=<closing.id>
      4) close again
    """
    if not _try_lock_month(db, year, month):
        raise ValueError(f"Period {year}-{month:02d} is busy; try again shortly.")

    try:
        reopen_period(db, year, month, note=note or "reclose")

        ref = f"CLOSE-{year:04d}{month:02d}"
        closing_ids: List[int] = db.execute(
            select(JournalEntry.id).where(
                JournalEntry.reference_no == ref,
                JournalEntry.is_locked.is_(True),
            )
        ).scalars().all()

        if closing_ids:
            last = date(year, month, calendar.monthrange(year, month)[1])
            for cid in closing_ids:
                if not _has_posted_reversal_for(db, cid):
                    reverse_journal_entry(db, cid, as_of=last, created_by_user_id=created_by_user_id)

        return close_period(
            db,
            year,
            month,
            equity_account_id=equity_account_id,
            note=note or "reclosed",
            created_by_user_id=created_by_user_id,
        )
    finally:
        _unlock_month(db, year, month)
