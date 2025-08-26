from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

def _first_of_month(d: date) -> date:
    return date(d.year, d.month, 1)

def _is_period_locked(db: Session, d: date) -> bool:
    """
    True if the month containing 'd' is locked in gl_period_locks.
    Uses a lightweight raw SQL check (no ORM model required).
    """
    sql = text(
        """
        SELECT is_locked
        FROM gl_period_locks
        WHERE period_month = :period_month
        LIMIT 1
        """
    )
    row = db.execute(sql, {"period_month": _first_of_month(d)}).first()
    return bool(row and row[0])

def _set_period_lock(db: Session, first: date, is_locked: bool, note: Optional[str] = None) -> None:
    sql = text(
        """
        INSERT INTO gl_period_locks (period_month, is_locked, note)
        VALUES (:pm, :locked, :note)
        ON CONFLICT (period_month)
        DO UPDATE SET is_locked = EXCLUDED.is_locked,
                      note      = COALESCE(EXCLUDED.note, gl_period_locks.note)
        """
    )
    db.execute(sql, {"pm": first, "locked": is_locked, "note": note})
    db.commit()
