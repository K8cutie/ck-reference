# app/api/gl_locks.py
from __future__ import annotations

from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.dependencies import get_db

router = APIRouter(prefix="/gl/locks", tags=["Accounting (Period Locks)"])


class LockItem(BaseModel):
    period_month: date
    is_locked: bool
    note: str | None = None


def _first_of_month(y: int, m: int) -> date:
    if not (1 <= m <= 12):
        raise HTTPException(status_code=400, detail="Invalid month (1-12 required).")
    return date(y, m, 1)


@router.get("", response_model=list[LockItem])
def list_locks(db: Session = Depends(get_db)):
    sql = text(
        """
        SELECT period_month, is_locked, note
        FROM gl_period_locks
        ORDER BY period_month
        """
    )
    rows = db.execute(sql).all()
    return [
        LockItem(period_month=r[0], is_locked=bool(r[1]), note=r[2]) for r in rows
    ]


@router.put("/{year}-{month}", response_model=LockItem)
def lock_month(year: int, month: int, db: Session = Depends(get_db), note: str | None = None):
    pm = _first_of_month(year, month)
    sql = text(
        """
        INSERT INTO gl_period_locks (period_month, is_locked, note)
        VALUES (:pm, TRUE, :note)
        ON CONFLICT (period_month)
        DO UPDATE SET is_locked = EXCLUDED.is_locked,
                      note      = COALESCE(EXCLUDED.note, gl_period_locks.note)
        RETURNING period_month, is_locked, note
        """
    )
    row = db.execute(sql, {"pm": pm, "note": note}).first()
    db.commit()
    return LockItem(period_month=row[0], is_locked=bool(row[1]), note=row[2])


@router.delete("/{year}-{month}", response_model=LockItem)
def unlock_month(year: int, month: int, db: Session = Depends(get_db)):
    pm = _first_of_month(year, month)
    sql = text(
        """
        INSERT INTO gl_period_locks (period_month, is_locked, note)
        VALUES (:pm, FALSE, NULL)
        ON CONFLICT (period_month)
        DO UPDATE SET is_locked = FALSE
        RETURNING period_month, is_locked, note
        """
    )
    row = db.execute(sql, {"pm": pm}).first()
    db.commit()
    return LockItem(period_month=row[0], is_locked=bool(row[1]), note=row[2])
