from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select, func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.transactions import Transaction, TransactionType
from app.models.account import Account
from app.models.fund import Fund
from app.schemas.transfer import TransferCreate, TransferOut, VoidTransfer

router = APIRouter(prefix="/transfers", tags=["Transfers"])


# --- helpers -----------------------------------------------------------------
def _ensure_account(db: Session, account_id: int) -> None:
    if account_id is None:
        raise HTTPException(status_code=422, detail="account_id is required")
    if db.get(Account, account_id) is None:
        raise HTTPException(status_code=422, detail=f"Account {account_id} not found")

def _ensure_fund_if_any(db: Session, fund_id: Optional[int]) -> None:
    if fund_id is None:
        return
    if db.get(Fund, fund_id) is None:
        raise HTTPException(status_code=422, detail=f"Fund {fund_id} not found")

def _ensure_reference_free(db: Session, ref: Optional[str], tx_type: TransactionType) -> None:
    """Enforce uniqueness of (type, reference_no) among NOT voided rows, if a ref is provided."""
    if not ref:
        return
    stmt = select(func.count()).select_from(Transaction).where(
        Transaction.type == tx_type,
        Transaction.reference_no == ref,
        Transaction.voided.is_(False),
    )
    if db.execute(stmt).scalar_one():
        raise HTTPException(status_code=409, detail=f"reference_no '{ref}' already in use for {tx_type.value}")

def _ensure_transfer_ref_free(db: Session, transfer_ref: Optional[str]) -> None:
    if not transfer_ref:
        return
    stmt = select(func.count()).select_from(Transaction).where(
        Transaction.transfer_ref == transfer_ref,
        Transaction.voided.is_(False),
    )
    if db.execute(stmt).scalar_one():
        raise HTTPException(status_code=409, detail=f"transfer_ref '{transfer_ref}' already exists")

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# --- routes ------------------------------------------------------------------
@router.post("/", response_model=TransferOut, status_code=status.HTTP_201_CREATED)
def create_transfer(payload: TransferCreate, db: Session = Depends(get_db)) -> TransferOut:
    if payload.from_account_id == payload.to_account_id:
        raise HTTPException(status_code=422, detail="from_account_id and to_account_id must differ")

    _ensure_account(db, payload.from_account_id)
    _ensure_account(db, payload.to_account_id)
    _ensure_fund_if_any(db, payload.fund_id)

    _ensure_reference_free(db, payload.reference_no_from, TransactionType.expense)
    _ensure_reference_free(db, payload.reference_no_to, TransactionType.income)
    _ensure_transfer_ref_free(db, payload.transfer_ref)

    # Pick a transfer_ref if none provided
    # We'll temporarily create one after flush using the expense tx id
    transfer_ref = payload.transfer_ref

    # Build description
    desc = payload.description or "Transfer"

    # Create both sides atomically
    expense_tx = Transaction(
        date=payload.date,
        description=desc,
        amount=payload.amount,
        type=TransactionType.expense,
        account_id=payload.from_account_id,
        fund_id=payload.fund_id,
        transfer_ref=transfer_ref,  # may still be None; we'll fill after flush
        batch_id=payload.batch_id,
        reference_no=payload.reference_no_from,
    )
    income_tx = Transaction(
        date=payload.date,
        description=desc,
        amount=payload.amount,
        type=TransactionType.income,
        account_id=payload.to_account_id,
        fund_id=payload.fund_id,
        transfer_ref=transfer_ref,
        batch_id=payload.batch_id,
        reference_no=payload.reference_no_to,
    )

    db.add_all([expense_tx, income_tx])
    db.flush()  # get IDs

    if transfer_ref is None:
        # Deterministic: use "XFER-{expense_id}"
        transfer_ref = f"XFER-{expense_tx.id}"
        expense_tx.transfer_ref = transfer_ref
        income_tx.transfer_ref = transfer_ref
        db.add_all([expense_tx, income_tx])

    db.commit()
    # Re-load to ensure latest
    db.refresh(expense_tx)
    db.refresh(income_tx)

    return TransferOut(
        transfer_ref=transfer_ref,
        date=payload.date,
        amount=payload.amount,
        description=desc,
        fund_id=payload.fund_id,
        from_account_id=expense_tx.account_id,
        to_account_id=income_tx.account_id,
        expense_tx_id=expense_tx.id,
        income_tx_id=income_tx.id,
        batch_id=payload.batch_id,
    )


@router.get("/", response_model=List[TransferOut])
def list_transfers(
    db: Session = Depends(get_db),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    account_id: Optional[int] = Query(None, description="Show transfers touching this account"),
    transfer_ref: Optional[str] = Query(None),
    limit: int = Query(200, le=500),
    skip: int = 0,
) -> List[TransferOut]:
    conds = [Transaction.transfer_ref.is_not(None), Transaction.voided.is_(False)]

    if date_from is not None:
        conds.append(Transaction.date >= date_from.date())
    if date_to is not None:
        conds.append(Transaction.date <= date_to.date())
    if account_id is not None:
        conds.append(Transaction.account_id == account_id)
    if transfer_ref:
        conds.append(Transaction.transfer_ref == transfer_ref)

    stmt = (
        select(Transaction)
        .where(and_(*conds))
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .offset(skip)
        .limit(limit * 2)  # two rows per transfer, roughly
    )
    txs = db.execute(stmt).scalars().all()

    grouped: Dict[str, Dict[str, Transaction | None]] = {}
    for tx in txs:
        ref = tx.transfer_ref
        if not ref:
            continue
        g = grouped.setdefault(ref, {"expense": None, "income": None})
        if tx.type == TransactionType.expense and g["expense"] is None:
            g["expense"] = tx
        elif tx.type == TransactionType.income and g["income"] is None:
            g["income"] = tx

    out: List[TransferOut] = []
    for ref, pair in grouped.items():
        exp = pair["expense"]
        inc = pair["income"]
        # Only show complete pairs; if you want partials, remove this guard.
        if not exp or not inc:
            continue
        out.append(
            TransferOut(
                transfer_ref=ref,
                date=exp.date,
                amount=exp.amount,
                description=exp.description,
                fund_id=exp.fund_id or inc.fund_id,
                from_account_id=exp.account_id,
                to_account_id=inc.account_id,
                expense_tx_id=exp.id,
                income_tx_id=inc.id,
                batch_id=exp.batch_id or inc.batch_id,
            )
        )
    return out


@router.post("/{transfer_ref}/void", response_model=TransferOut)
def void_transfer(transfer_ref: str, body: VoidTransfer | None = None, db: Session = Depends(get_db)) -> TransferOut:
    # Find both sides (if any) that are not voided yet
    stmt = select(Transaction).where(
        Transaction.transfer_ref == transfer_ref,
        Transaction.voided.is_(False),
    )
    txs = db.execute(stmt).scalars().all()
    if not txs:
        # Maybe already voided — try to fetch any to return state
        stmt_any = select(Transaction).where(Transaction.transfer_ref == transfer_ref).limit(2)
        any_txs = db.execute(stmt_any).scalars().all()
        if not any_txs:
            raise HTTPException(status_code=404, detail="Transfer not found")
        # Already voided; fabricate a response from the (now voided) rows
        exp = next((t for t in any_txs if t.type == TransactionType.expense), None)
        inc = next((t for t in any_txs if t.type == TransactionType.income), None)
        return TransferOut(
            transfer_ref=transfer_ref,
            date=(exp or inc).date,
            amount=(exp or inc).amount,
            description=(exp or inc).description,
            fund_id=(exp or inc).fund_id,
            from_account_id=exp.account_id if exp else None,
            to_account_id=inc.account_id if inc else None,
            expense_tx_id=exp.id if exp else None,
            income_tx_id=inc.id if inc else None,
            batch_id=(exp or inc).batch_id,
        )

    reason = (body.reason if body else None) or f"Transfer {transfer_ref} voided"
    now = _now_utc()
    for t in txs:
        t.voided = True
        t.voided_at = now
        t.void_reason = reason
        db.add(t)

    db.commit()

    # Return what we can (use the rows we just modified)
    exp = next((t for t in txs if t.type == TransactionType.expense), None)
    inc = next((t for t in txs if t.type == TransactionType.income), None)
    any_t = exp or inc
    return TransferOut(
        transfer_ref=transfer_ref,
        date=any_t.date,
        amount=any_t.amount,
        description=any_t.description,
        fund_id=any_t.fund_id,
        from_account_id=exp.account_id if exp else None,
        to_account_id=inc.account_id if inc else None,
        expense_tx_id=exp.id if exp else None,
        income_tx_id=inc.id if inc else None,
        batch_id=any_t.batch_id,
    )
