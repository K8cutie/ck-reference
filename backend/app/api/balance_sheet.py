# app/api/balance_sheet.py
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import case, func, select, cast, Numeric, literal
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

class BSRow(BaseModel):
    account_id: int
    code: str
    name: str
    type: str
    normal_side: str
    # Signed balance by normal side convention (debit-normal => debits-credits; credit-normal => credits-debits)
    balance: float
    # Split for UI
    dr_balance: float
    cr_balance: float

class BalanceSheetOut(BaseModel):
    as_of: Optional[date] = None
    assets: List[BSRow]
    liabilities: List[BSRow]
    equity: List[BSRow]
    totals: dict  # {assets, liabilities, equity, liabilities_plus_equity}


# ---------- Helpers ----------

def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).date()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid date: {s}") from e


# ---------- Route ----------

@router.get("/balance_sheet", response_model=BalanceSheetOut)
def balance_sheet(
    as_of: Optional[str] = Query(None, description="YYYY-MM-DD (inclusive). If omitted, uses all posted JEs."),
    db: Session = Depends(get_db),
):
    """
    Balance Sheet as of a date (<= as_of), considering **posted** Journal Entries only.
    - balance (signed) uses account normal side:
        * debit-normal:  debits - credits
        * credit-normal: credits - debits
    - For display/totals:
        * Assets total = sum(dr_balance of asset accounts)
        * Liabilities total = sum(cr_balance of liability accounts)
        * Equity total = sum(cr_balance of equity accounts)
    """
    as_of_date = _parse_date(as_of)

    filters = [JournalEntry.posted_at.isnot(None)]
    if as_of_date is not None:
        filters.append(JournalEntry.entry_date <= as_of_date)

    debit_sum = func.coalesce(func.sum(JournalLine.debit), 0.0)
    credit_sum = func.coalesce(func.sum(JournalLine.credit), 0.0)

    # Signed balance per account by normal side
    balance_expr = case(
        (GLAccount.normal_side == "debit",  debit_sum - credit_sum),
        (GLAccount.normal_side == "credit", credit_sum - debit_sum),
        else_=cast(literal(0.0), Numeric(14, 2)),
    )

    q = (
        select(
            GLAccount.id.label("account_id"),
            GLAccount.code.label("code"),
            GLAccount.name.label("name"),
            GLAccount.type.label("type"),
            GLAccount.normal_side.label("normal_side"),
            balance_expr.label("balance"),
        )
        .select_from(GLAccount)
        .join(JournalLine, JournalLine.account_id == GLAccount.id, isouter=True)
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id, isouter=True)
        .where(GLAccount.type.in_(["asset", "liability", "equity"]), *filters)
        .group_by(GLAccount.id, GLAccount.code, GLAccount.name, GLAccount.type, GLAccount.normal_side)
        .order_by(GLAccount.code.asc())
    )

    res = db.execute(q).all()

    assets: List[BSRow] = []
    liabilities: List[BSRow] = []
    equity: List[BSRow] = []

    total_assets = 0.0
    total_liabilities = 0.0
    total_equity = 0.0

    for r in res:
        bal = float(r.balance or 0.0)
        # Split DR/CR balance for UI (positive in its own column)
        if (r.normal_side or "").lower() == "debit":
            dr_bal = max(bal, 0.0)
            cr_bal = 0.0 if bal >= 0 else -bal
        else:
            cr_bal = max(bal, 0.0)
            dr_bal = 0.0 if bal >= 0 else -bal

        row = BSRow(
            account_id=r.account_id,
            code=r.code,
            name=r.name,
            type=r.type,
            normal_side=r.normal_side,
            balance=round(bal, 2),
            dr_balance=round(dr_bal, 2),
            cr_balance=round(cr_bal, 2),
        )

        # Only include rows with a non-zero absolute balance (cleaner BS)
        if abs(row.balance) < 0.0005:
            continue

        if r.type == "asset":
            assets.append(row)
            total_assets += row.dr_balance  # assets show on debit side
        elif r.type == "liability":
            liabilities.append(row)
            total_liabilities += row.cr_balance  # liabilities show on credit side
        else:  # equity
            equity.append(row)
            total_equity += row.cr_balance  # equity shows on credit side

    payload = BalanceSheetOut(
        as_of=as_of_date,
        assets=assets,
        liabilities=liabilities,
        equity=equity,
        totals={
            "assets": round(total_assets, 2),
            "liabilities": round(total_liabilities, 2),
            "equity": round(total_equity, 2),
            "liabilities_plus_equity": round(total_liabilities + total_equity, 2),
        },
    )
    return payload
