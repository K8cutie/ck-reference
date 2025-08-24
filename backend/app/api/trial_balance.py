# app/api/trial_balance.py
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.gl_accounting import GLAccount, JournalEntry, JournalLine

router = APIRouter(prefix="/gl/reports", tags=["GL • Reports"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- Schemas ----------

class TrialBalanceRow(BaseModel):
    account_id: int
    code: str
    name: str
    type: str
    normal_side: str
    debit_total: float
    credit_total: float
    # Signed ending balance computed by normal side convention
    balance: float
    # For UI convenience:
    dr_balance: float
    cr_balance: float


class TrialBalanceOut(BaseModel):
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    rows: List[TrialBalanceRow]
    totals: dict


# ---------- Helpers ----------

def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).date()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid date: {s}") from e


# ---------- Route ----------

@router.get("/trial_balance", response_model=TrialBalanceOut)
def trial_balance(
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD (inclusive)"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD (inclusive)"),
    db: Session = Depends(get_db),
):
    """
    Trial Balance over posted Journal Entries only.
    - If no range provided, computes for ALL posted entries.
    - balance = (debits - credits) for normal_side=debit, else (credits - debits).
    """
    d_from = _parse_date(date_from)
    d_to = _parse_date(date_to)

    # Build filters for date range (inclusive)
    filters = [JournalEntry.posted_at.isnot(None)]
    if d_from is not None:
        filters.append(JournalEntry.entry_date >= d_from)
    if d_to is not None:
        filters.append(JournalEntry.entry_date <= d_to)

    # Aggregate per account
    debit_sum = func.coalesce(func.sum(JournalLine.debit), 0.0)
    credit_sum = func.coalesce(func.sum(JournalLine.credit), 0.0)

    q = (
        select(
            GLAccount.id.label("account_id"),
            GLAccount.code.label("code"),
            GLAccount.name.label("name"),
            GLAccount.type.label("type"),
            GLAccount.normal_side.label("normal_side"),
            debit_sum.label("debit_total"),
            credit_sum.label("credit_total"),
        )
        .select_from(GLAccount)
        .join(JournalLine, JournalLine.account_id == GLAccount.id, isouter=True)
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id, isouter=True)
        .where(*filters)  # filters apply to left-joined rows; rows without entries → NULL deb/cred and sum→0
        .group_by(GLAccount.id, GLAccount.code, GLAccount.name, GLAccount.type, GLAccount.normal_side)
        .order_by(GLAccount.code.asc())
    )

    rows = []
    res = db.execute(q).all()

    total_debits = 0.0
    total_credits = 0.0
    total_dr_balance = 0.0
    total_cr_balance = 0.0

    for r in res:
        debit_total = float(r.debit_total or 0.0)
        credit_total = float(r.credit_total or 0.0)
        normal = (r.normal_side or "").lower()

        # Signed balance by account's normal side
        if normal == "debit":
            bal = debit_total - credit_total
            dr_bal = max(bal, 0.0)
            cr_bal = 0.0 if bal >= 0 else -bal
        else:
            bal = credit_total - debit_total
            cr_bal = max(bal, 0.0)
            dr_bal = 0.0 if bal >= 0 else -bal

        rows.append(
            TrialBalanceRow(
                account_id=r.account_id,
                code=r.code,
                name=r.name,
                type=r.type,
                normal_side=r.normal_side,
                debit_total=debit_total,
                credit_total=credit_total,
                balance=bal,
                dr_balance=dr_bal,
                cr_balance=cr_bal,
            )
        )

        total_debits += debit_total
        total_credits += credit_total
        total_dr_balance += dr_bal
        total_cr_balance += cr_bal

    return TrialBalanceOut(
        date_from=d_from,
        date_to=d_to,
        rows=rows,
        totals={
            "debit_total": round(total_debits, 2),
            "credit_total": round(total_credits, 2),
            "dr_balance": round(total_dr_balance, 2),
            "cr_balance": round(total_cr_balance, 2),
        },
    )
