from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.pledge import Pledge  # enums optional; we won't depend on their names
from app.models.transactions import Transaction, TransactionType
from app.models.account import Account
from app.models.fund import Fund
from app.models.compliance import ComplianceConfig

router = APIRouter(prefix="/pledges", tags=["Pledges"])


# --- helpers -----------------------------------------------------------------
def _hard_delete_allowed(db: Session) -> bool:
    cfg = db.get(ComplianceConfig, 1)
    return bool(cfg and cfg.allow_hard_delete)


def _to_float(x) -> float:
    if x is None:
        return 0.0
    if isinstance(x, Decimal):
        return float(x)
    return float(x)


def _income_type() -> str | TransactionType:
    # Use enum if present; else fall back to string
    try:
        return TransactionType.income
    except Exception:  # pragma: no cover
        return "income"


# --- minimal endpoints (existing ones can stay elsewhere) --------------------
@router.get("/", summary="List pledges (lightweight)")
def list_pledges(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = Query(50, le=200),
):
    stmt = (
        select(Pledge)
        .order_by(Pledge.pledge_date.desc(), Pledge.id.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = db.execute(stmt).scalars().all()

    # Attach paid_total per pledge
    ids = [p.id for p in rows]
    if ids:
        paid_stmt = (
            select(Transaction.pledge_id, func.coalesce(func.sum(Transaction.amount), 0))
            .where(
                Transaction.pledge_id.in_(ids),
                Transaction.type == _income_type(),
                Transaction.voided.is_(False),
            )
            .group_by(Transaction.pledge_id)
        )
        paid_map = {pid: amt for pid, amt in db.execute(paid_stmt).all()}
    else:
        paid_map = {}

    out = []
    for p in rows:
        out.append(
            {
                "id": p.id,
                "parishioner_id": p.parishioner_id,
                "fund_id": p.fund_id,
                "pledge_date": str(p.pledge_date),
                "amount_total": _to_float(p.amount_total),
                "frequency": getattr(p, "frequency", None),
                "status": getattr(p, "status", None),
                "start_date": getattr(p, "start_date", None),
                "end_date": getattr(p, "end_date", None),
                "notes": getattr(p, "notes", None),
                "paid_total": _to_float(paid_map.get(p.id, 0)),
            }
        )
    return out


@router.get("/{pledge_id}")
def get_pledge(pledge_id: int, db: Session = Depends(get_db)):
    p = db.get(Pledge, pledge_id)
    if not p:
        raise HTTPException(status_code=404, detail="Pledge not found")

    paid_stmt = (
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(
            Transaction.pledge_id == pledge_id,
            Transaction.type == _income_type(),
            Transaction.voided.is_(False),
        )
    )
    paid_total = db.execute(paid_stmt).scalar_one()

    return {
        "id": p.id,
        "parishioner_id": p.parishioner_id,
        "fund_id": p.fund_id,
        "pledge_date": str(p.pledge_date),
        "amount_total": _to_float(p.amount_total),
        "frequency": getattr(p, "frequency", None),
        "status": getattr(p, "status", None),
        "start_date": getattr(p, "start_date", None),
        "end_date": getattr(p, "end_date", None),
        "notes": getattr(p, "notes", None),
        "paid_total": _to_float(paid_total),
    }


@router.post("/{pledge_id}/record_payment", status_code=status.HTTP_201_CREATED)
def record_payment(
    pledge_id: int,
    db: Session = Depends(get_db),
    date_: date = Query(..., alias="date"),
    amount: Decimal = Query(...),
    account_id: int = Query(...),
    fund_id: Optional[int] = None,
    reference_no: Optional[str] = None,
    payment_method: Optional[str] = None,
    description: Optional[str] = "Pledge payment",
):
    p = db.get(Pledge, pledge_id)
    if not p:
        raise HTTPException(status_code=404, detail="Pledge not found")

    acct = db.get(Account, account_id)
    if not acct:
        raise HTTPException(status_code=422, detail="account_id does not exist")

    if fund_id is None:
        fund_id = p.fund_id
    if fund_id is not None and not db.get(Fund, fund_id):
        raise HTTPException(status_code=422, detail="fund_id does not exist")

    # disallow duplicate active OR numbers
    if reference_no:
        dup = db.execute(
            select(func.count())
            .select_from(Transaction)
            .where(
                Transaction.type == _income_type(),
                Transaction.reference_no == reference_no,
                Transaction.voided.is_(False),
            )
        ).scalar_one()
        if dup:
            raise HTTPException(status_code=409, detail="reference_no already used by an active income transaction")

    tx = Transaction(
        date=date_,
        description=description,
        amount=amount,
        type=_income_type(),
        category_id=None,
        parishioner_id=p.parishioner_id,
        account_id=account_id,
        fund_id=fund_id,
        pledge_id=pledge_id,
        payment_method=(payment_method.lower() if payment_method else None),
        reference_no=reference_no,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)

    return {
        "id": tx.id,
        "date": str(tx.date),
        "amount": _to_float(tx.amount),
        "type": tx.type.value if hasattr(tx.type, "value") else str(tx.type),
        "account_id": tx.account_id,
        "fund_id": tx.fund_id,
        "pledge_id": tx.pledge_id,
        "reference_no": tx.reference_no,
        "payment_method": getattr(tx, "payment_method", None),
    }


@router.delete("/{pledge_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Hard-delete a pledge (gated by compliance)")
def delete_pledge(pledge_id: int, db: Session = Depends(get_db)) -> Response:
    p = db.get(Pledge, pledge_id)
    if not p:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    if not _hard_delete_allowed(db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Hard delete is disabled by compliance policy. "
                "If this pledge is erroneous, consider leaving it but voiding any related payments. "
                "An admin may temporarily enable allow_hard_delete via PATCH /compliance/config."
            ),
        )

    # Optional safety: prevent delete if it has non-voided payments
    has_active_payments = db.execute(
        select(func.count())
        .select_from(Transaction)
        .where(
            Transaction.pledge_id == pledge_id,
            Transaction.type == _income_type(),
            Transaction.voided.is_(False),
        )
    ).scalar_one()
    if has_active_payments:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete pledge with active (non-voided) payments. Void or delete those transactions first.",
        )

    db.delete(p)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
