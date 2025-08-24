# app/api/income_statement.py
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

class StatementRow(BaseModel):
    account_id: int
    code: str
    name: str
    amount: float  # positive = normal direction (income: credit>debit; expense: debit>credit)

class IncomeStatementOut(BaseModel):
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    incomes: List[StatementRow]
    expenses: List[StatementRow]
    totals: dict  # {income_total, expense_total, net_income}


# ---------- Helpers ----------

def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).date()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid date: {s}") from e


# ---------- Route ----------

@router.get("/income_statement", response_model=IncomeStatementOut)
def income_statement(
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD (inclusive)"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD (inclusive)"),
    db: Session = Depends(get_db),
):
    """
    Profit & Loss (Income Statement) based on **posted** Journal Entries.
    - If no range is provided, computes over ALL posted entries.
    - Income account amount  = SUM(credits - debits)
    - Expense account amount = SUM(debits - credits)
    """
    d_from = _parse_date(date_from)
    d_to = _parse_date(date_to)

    filters = [JournalEntry.posted_at.isnot(None)]
    if d_from is not None:
        filters.append(JournalEntry.entry_date >= d_from)
    if d_to is not None:
        filters.append(JournalEntry.entry_date <= d_to)

    # Aggregate sums per account
    debit_sum = func.coalesce(func.sum(JournalLine.debit), 0.0)
    credit_sum = func.coalesce(func.sum(JournalLine.credit), 0.0)

    # Signed amount per account depending on account type
    amount_expr = case(
        (GLAccount.type == "income", credit_sum - debit_sum),
        (GLAccount.type == "expense", debit_sum - credit_sum),
        else_=cast(literal(0.0), Numeric(14, 2)),
    )

    q = (
        select(
            GLAccount.id.label("account_id"),
            GLAccount.code.label("code"),
            GLAccount.name.label("name"),
            GLAccount.type.label("type"),
            amount_expr.label("amount"),
        )
        .select_from(GLAccount)
        .join(JournalLine, JournalLine.account_id == GLAccount.id, isouter=True)
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id, isouter=True)
        .where(GLAccount.type.in_(["income", "expense"]), *filters)
        .group_by(GLAccount.id, GLAccount.code, GLAccount.name, GLAccount.type)
        .order_by(GLAccount.code.asc())
    )

    res = db.execute(q).all()

    incomes: List[StatementRow] = []
    expenses: List[StatementRow] = []
    income_total = 0.0
    expense_total = 0.0

    for r in res:
        amt = float(r.amount or 0.0)
        row = StatementRow(account_id=r.account_id, code=r.code, name=r.name, amount=round(amt, 2))
        if r.type == "income":
            incomes.append(row)
            income_total += amt
        else:
            expenses.append(row)
            expense_total += amt

    return IncomeStatementOut(
        date_from=d_from,
        date_to=d_to,
        incomes=incomes,
        expenses=expenses,
        totals={
            "income_total": round(income_total, 2),
            "expense_total": round(expense_total, 2),
            "net_income": round(income_total - expense_total, 2),
        },
    )
