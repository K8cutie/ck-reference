# backend/app/api/reports.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.orm import Session

from app.db import get_db

# Models
from app.models.expense import Expense, ExpenseStatus as ModelExpenseStatus
try:
    from app.models.category import Category
except ModuleNotFoundError:
    from app.models.categories import Category
from app.models.transactions import Transaction, TransactionType
from app.models.account import Account
from app.models.fund import Fund

router = APIRouter(prefix="/reports", tags=["Reports"])


# ---------- helpers ----------
def _like(q: str) -> str:
    return f"%{q}%"


def _to_float(x) -> float:
    if x is None:
        return 0.0
    if isinstance(x, Decimal):
        return float(x)
    return float(x)


# ---------- /reports/expenses/summary ----------
@router.get("/expenses/summary")
def expenses_summary(
    db: Session = Depends(get_db),
    q: Optional[str] = Query(None, description="Search vendor/description/reference"),
    status_: Optional[ModelExpenseStatus] = Query(None, alias="status"),
    category_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
):
    conds = []
    if q:
        like = _like(q)
        conds.append(
            or_(
                Expense.vendor_name.ilike(like),
                Expense.description.ilike(like),
                Expense.reference_no.ilike(like),
            )
        )
    if status_ is not None:
        conds.append(Expense.status == status_)
    if category_id is not None:
        conds.append(Expense.category_id == category_id)
    if date_from is not None:
        conds.append(Expense.expense_date >= date_from)
    if date_to is not None:
        conds.append(Expense.expense_date <= date_to)

    where_clause = and_(*conds) if conds else True

    # totals
    totals_stmt = select(
        func.count(Expense.id),
        func.coalesce(func.sum(Expense.amount), 0),
    ).where(where_clause)
    total_count, total_amount = db.execute(totals_stmt).one()

    # by status
    by_status_stmt = (
        select(
            Expense.status,
            func.count(Expense.id),
            func.coalesce(func.sum(Expense.amount), 0),
        )
        .where(where_clause)
        .group_by(Expense.status)
    )
    by_status_rows = db.execute(by_status_stmt).all()
    by_status = {
        str(row[0]): {"count": row[1], "amount": _to_float(row[2])}
        for row in by_status_rows
    }

    # by category
    by_category_stmt = (
        select(
            Category.id,
            Category.name,
            func.count(Expense.id),
            func.coalesce(func.sum(Expense.amount), 0),
        )
        .join(Category, Category.id == Expense.category_id, isouter=True)
        .where(where_clause)
        .group_by(Category.id, Category.name)
        .order_by(func.coalesce(func.sum(Expense.amount), 0).desc())
    )
    by_category_rows = db.execute(by_category_stmt).all()
    by_category = [
        {
            "category_id": cid,
            "category_name": cname,
            "count": cnt,
            "amount": _to_float(amt),
        }
        for cid, cname, cnt, amt in by_category_rows
    ]

    return {
        "filters": {
            "q": q,
            "status": str(status_) if status_ is not None else None,
            "category_id": category_id,
            "date_from": str(date_from) if date_from else None,
            "date_to": str(date_to) if date_to else None,
        },
        "totals": {"count": total_count, "amount": _to_float(total_amount)},
        "by_status": by_status,
        "by_category": by_category,
    }


# ---------- /reports/expenses/export.csv ----------
@router.get("/expenses/export.csv")
def expenses_export_csv(
    db: Session = Depends(get_db),
    q: Optional[str] = Query(None),
    status_: Optional[ModelExpenseStatus] = Query(None, alias="status"),
    category_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
):
    conds = []
    if q:
        like = _like(q)
        conds.append(
            or_(
                Expense.vendor_name.ilike(like),
                Expense.description.ilike(like),
                Expense.reference_no.ilike(like),
            )
        )
    if status_ is not None:
        conds.append(Expense.status == status_)
    if category_id is not None:
        conds.append(Expense.category_id == category_id)
    if date_from is not None:
        conds.append(Expense.expense_date >= date_from)
    if date_to is not None:
        conds.append(Expense.expense_date <= date_to)

    where_clause = and_(*conds) if conds else True

    stmt = (
        select(
            Expense.id,
            Expense.expense_date,
            Expense.amount,
            Expense.status,
            Expense.vendor_name,
            Expense.description,
            Expense.payment_method,
            Expense.reference_no,
            Category.name.label("category_name"),
            Expense.paid_at,
            Expense.created_at,
            Expense.updated_at,
        )
        .join(Category, Category.id == Expense.category_id, isouter=True)
        .where(where_clause)
        .order_by(Expense.expense_date.asc(), Expense.id.asc())
    )

    def row_iter():
        cols = [
            "id",
            "expense_date",
            "amount",
            "status",
            "vendor_name",
            "description",
            "payment_method",
            "reference_no",
            "category_name",
            "paid_at",
            "created_at",
            "updated_at",
        ]
        yield ",".join(cols) + "\n"

        result = db.execute(stmt)
        for r in result:
            def esc(val):
                if val is None:
                    return ""
                s = str(val)
                if any(c in s for c in [",", '"', "\n", "\r"]):
                    s = '"' + s.replace('"', '""') + '"'
                return s

            row = [
                esc(r.id),
                esc(r.expense_date),
                esc(_to_float(r.amount)),
                esc(r.status),
                esc(r.vendor_name or ""),
                esc(r.description or ""),
                esc(r.payment_method or ""),
                esc(r.reference_no or ""),
                esc(r.category_name or ""),
                esc(r.paid_at or ""),
                esc(r.created_at or ""),
                esc(r.updated_at or ""),
            ]
            yield ",".join(row) + "\n"

    return StreamingResponse(
        row_iter(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="expenses_export.csv"'},
    )


# ---------- /reports/accounts/balances ----------
@router.get("/accounts/balances")
def accounts_balances(
    db: Session = Depends(get_db),
    as_of: date = Query(default_factory=date.today),
    active_only: bool = True,
):
    inflow = func.coalesce(
        func.sum(case((Transaction.type == TransactionType.income, Transaction.amount), else_=0)),
        0,
    )
    outflow = func.coalesce(
        func.sum(case((Transaction.type == TransactionType.expense, Transaction.amount), else_=0)),
        0,
    )

    stmt = (
        select(
            Account.id,
            Account.name,
            Account.currency,
            Account.opening_balance,
            inflow.label("inflow"),
            outflow.label("outflow"),
            (Account.opening_balance + inflow - outflow).label("balance"),
        )
        .outerjoin(
            Transaction,
            and_(
                Transaction.account_id == Account.id,
                Transaction.voided.is_(False),
                Transaction.date <= as_of,
            ),
        )
        .where(Account.active.is_(True) if active_only else True)
        .group_by(Account.id)
        .order_by(Account.name.asc())
    )

    rows = db.execute(stmt).all()
    items = [
        {
            "account_id": rid,
            "name": nm,
            "currency": cur,
            "opening_balance": _to_float(ob),
            "inflow": _to_float(inn),
            "outflow": _to_float(outt),
            "balance": _to_float(bal),
        }
        for rid, nm, cur, ob, inn, outt, bal in rows
    ]

    totals = {
        "opening_balance": _to_float(sum(Decimal(str(i["opening_balance"])) for i in items)),
        "inflow": _to_float(sum(Decimal(str(i["inflow"])) for i in items)),
        "outflow": _to_float(sum(Decimal(str(i["outflow"])) for i in items)),
        "balance": _to_float(sum(Decimal(str(i["balance"])) for i in items)),
    }

    return {"as_of": str(as_of), "accounts": items, "totals": totals}


# ---------- /reports/funds/summary ----------
@router.get("/funds/summary")
def funds_summary(
    db: Session = Depends(get_db),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    include_unassigned: bool = False,
):
    tx_on = [Transaction.fund_id == Fund.id, Transaction.voided.is_(False)]
    if date_from is not None:
        tx_on.append(Transaction.date >= date_from)
    if date_to is not None:
        tx_on.append(Transaction.date <= date_to)

    inflow = func.coalesce(
        func.sum(case((Transaction.type == TransactionType.income, Transaction.amount), else_=0)),
        0,
    )
    outflow = func.coalesce(
        func.sum(case((Transaction.type == TransactionType.expense, Transaction.amount), else_=0)),
        0,
    )

    stmt = (
        select(
            Fund.id,
            Fund.code,
            Fund.name,
            inflow.label("inflow"),
            outflow.label("outflow"),
            (inflow - outflow).label("net"),
        )
        .outerjoin(Transaction, and_(*tx_on))
        .group_by(Fund.id)
        .order_by(Fund.name.asc())
    )
    rows = db.execute(stmt).all()
    items = [
        {
            "fund_id": fid,
            "code": code,
            "name": name,
            "inflow": _to_float(inn),
            "outflow": _to_float(outt),
            "net": _to_float(net),
        }
        for fid, code, name, inn, outt, net in rows
    ]

    unassigned = None
    if include_unassigned:
        null_on = [Transaction.fund_id.is_(None), Transaction.voided.is_(False)]
        if date_from is not None:
            null_on.append(Transaction.date >= date_from)
        if date_to is not None:
            null_on.append(Transaction.date <= date_to)
        null_stmt = select(inflow, outflow).select_from(Transaction).where(and_(*null_on))
        inn, outt = db.execute(null_stmt).one()
        unassigned = {
            "fund_id": None,
            "code": None,
            "name": "Unassigned",
            "inflow": _to_float(inn),
            "outflow": _to_float(outt),
            "net": _to_float(inn) - _to_float(outt),
        }

    return {
        "date_from": str(date_from) if date_from else None,
        "date_to": str(date_to) if date_to else None,
        "funds": items,
        **({"unassigned": unassigned} if include_unassigned else {}),
    }


# ---------- /reports/accounts/balances.csv ----------
@router.get("/accounts/balances.csv")
def accounts_balances_csv(
    db: Session = Depends(get_db),
    as_of: date = Query(default_factory=date.today),
    active_only: bool = True,
):
    data = accounts_balances(db=db, as_of=as_of, active_only=active_only)  # reuse logic
    items = data["accounts"]
    totals = data["totals"]

    def row_iter():
        cols = ["account_id", "name", "currency", "opening_balance", "inflow", "outflow", "balance"]
        yield ",".join(cols) + "\n"

        def esc(v):
            if v is None:
                return ""
            s = str(v)
            if any(c in s for c in [",", '"', "\n", "\r"]):
                s = '"' + s.replace('"', '""') + '"'
            return s

        for i in items:
            row = [
                i["account_id"],
                i["name"],
                i["currency"],
                i["opening_balance"],
                i["inflow"],
                i["outflow"],
                i["balance"],
            ]
            yield ",".join(esc(x) for x in row) + "\n"

        t = totals
        total_row = ["", "TOTAL", "", t["opening_balance"], t["inflow"], t["outflow"], t["balance"]]
        yield ",".join(esc(x) for x in total_row) + "\n"

    return StreamingResponse(
        row_iter(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="accounts_balances.csv"'},
    )


# ---------- /reports/funds/summary.csv ----------
@router.get("/funds/summary.csv")
def funds_summary_csv(
    db: Session = Depends(get_db),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    include_unassigned: bool = False,
):
    data = funds_summary(
        db=db, date_from=date_from, date_to=date_to, include_unassigned=include_unassigned
    )  # reuse logic
    items = data["funds"]
    unassigned = data.get("unassigned")

    def row_iter():
        cols = ["fund_id", "code", "name", "inflow", "outflow", "net"]
        yield ",".join(cols) + "\n"

        def esc(v):
            if v is None:
                return ""
            s = str(v)
            if any(c in s for c in [",", '"', "\n", "\r"]):
                s = '"' + s.replace('"', '""') + '"'
            return s

        for i in items:
            row = [i["fund_id"], i["code"], i["name"], i["inflow"], i["outflow"], i["net"]]
            yield ",".join(esc(x) for x in row) + "\n"

        if include_unassigned and unassigned:
            u = unassigned
            row = [u["fund_id"], "", u["name"], u["inflow"], u["outflow"], u["net"]]
            yield ",".join(esc(x) for x in row) + "\n"

    return StreamingResponse(
        row_iter(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="funds_summary.csv"'},
    )
