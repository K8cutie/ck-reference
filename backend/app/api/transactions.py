from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.transactions import Transaction, TransactionType
from app.models.compliance import ComplianceConfig

router = APIRouter(prefix="/transactions", tags=["Transactions"])


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


# --- endpoints ---------------------------------------------------------------
@router.get("/", summary="List transactions (lightweight)")
def list_transactions(
    db: Session = Depends(get_db),
    q: Optional[str] = Query(None, description="Search description / reference / transfer"),
    type: Optional[TransactionType] = Query(None, description="'income' or 'expense'"),
    account_id: Optional[int] = None,
    fund_id: Optional[int] = None,
    pledge_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    skip: int = 0,
    limit: int = Query(50, le=1000),
):
    conds = []
    if q:
        like = f"%{q}%"
        conds.append(or_(
            Transaction.description.ilike(like),
            Transaction.reference_no.ilike(like),
            Transaction.transfer_ref.ilike(like),
        ))
    if type is not None:
        conds.append(Transaction.type == type)
    if account_id is not None:
        conds.append(Transaction.account_id == account_id)
    if fund_id is not None:
        conds.append(Transaction.fund_id == fund_id)
    if pledge_id is not None:
        conds.append(Transaction.pledge_id == pledge_id)
    if date_from is not None:
        conds.append(Transaction.date >= date_from)
    if date_to is not None:
        conds.append(Transaction.date <= date_to)

    where_clause = and_(*conds) if conds else True

    stmt = (
        select(Transaction)
        .where(where_clause)
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .offset(skip)
        .limit(limit)
    )
    rows: List[Transaction] = db.execute(stmt).scalars().all()
    return [
        {
            "id": r.id,
            "date": str(r.date),
            "description": r.description,
            "amount": _to_float(r.amount),
            "type": r.type.value if hasattr(r.type, "value") else str(r.type),
            "category_id": getattr(r, "category_id", None),       # <-- added
            "parishioner_id": getattr(r, "parishioner_id", None), # <-- added
            "account_id": r.account_id,
            "fund_id": r.fund_id,
            "pledge_id": r.pledge_id,
            "payment_method": getattr(r, "payment_method", None),
            "reference_no": r.reference_no,
            "transfer_ref": getattr(r, "transfer_ref", None),
            "reconciled": getattr(r, "reconciled", None),
            "voided": getattr(r, "voided", None),
            "voided_at": getattr(r, "voided_at", None),
        }
        for r in rows
    ]


@router.get("/{tx_id}")
def get_transaction(tx_id: int, db: Session = Depends(get_db)):
    tx = db.get(Transaction, tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {
        "id": tx.id,
        "date": str(tx.date),
        "description": tx.description,
        "amount": _to_float(tx.amount),
        "type": tx.type.value if hasattr(tx.type, "value") else str(tx.type),
        "category_id": getattr(tx, "category_id", None),         # <-- added
        "parishioner_id": getattr(tx, "parishioner_id", None),   # <-- added
        "account_id": tx.account_id,
        "fund_id": tx.fund_id,
        "pledge_id": tx.pledge_id,
        "payment_method": getattr(tx, "payment_method", None),
        "reference_no": tx.reference_no,
        "transfer_ref": getattr(tx, "transfer_ref", None),
        "reconciled": getattr(tx, "reconciled", None),
        "voided": getattr(tx, "voided", None),
        "voided_at": getattr(tx, "voided_at", None),
        "void_reason": getattr(tx, "void_reason", None),
    }


@router.delete("/{tx_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Hard-delete a transaction (gated by compliance)")
def delete_transaction(tx_id: int, db: Session = Depends(get_db)) -> Response:
    tx = db.get(Transaction, tx_id)
    if not tx:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    if not _hard_delete_allowed(db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Hard delete is disabled by compliance policy. "
                "Please void the transaction instead, or toggle allow_hard_delete via "
                "PATCH /compliance/config if you have permission."
            ),
        )

    db.delete(tx)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
