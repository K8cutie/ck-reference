# backend/app/api/expenses.py
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Iterable

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import and_, or_, select, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db import get_db
from app.models.expense import Expense, ExpenseStatus as ModelExpenseStatus
from app.schemas.expense import (
    ExpenseCreate,
    ExpenseOut,
    ExpenseUpdate,
    ExpenseStatus as SchemaExpenseStatus,
)

# --- Transactions model imports (support plural/singular filenames) ----------
try:
    from app.models.transactions import (
        Transaction,
        TransactionType,
        PaymentMethod as TxPaymentMethod,
    )
except ImportError:  # pragma: no cover
    from app.models.transaction import (
        Transaction,
        TransactionType,
        PaymentMethod as TxPaymentMethod,
    )

# Compliance config (DB-backed)
try:
    from app.models.compliance import ComplianceConfig
except Exception:
    ComplianceConfig = None  # if model not present, fall back to "locked down"

router = APIRouter(prefix="/expenses", tags=["Expenses"])


# --- helpers -----------------------------------------------------------------
def _ensure_category_exists(db: Session, category_id: Optional[int]) -> None:
    if category_id is None:
        return
    row = db.execute(
        text("SELECT 1 FROM categories WHERE id = :cid LIMIT 1"),
        {"cid": category_id},
    ).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="category_id does not exist",
        )


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _pm_to_enum(value: Optional[str]) -> Optional[TxPaymentMethod]:
    if not value:
        return None
    try:
        return TxPaymentMethod(value.lower())
    except Exception:
        return None


def _expense_ref(exp: Expense) -> str:
    return exp.reference_no or f"EXP-{exp.id}"


def _active_tx_by_ref(db: Session, ref: str) -> Optional[Transaction]:
    return db.execute(
        select(Transaction).where(
            Transaction.type == TransactionType.expense,
            Transaction.reference_no == ref,
            Transaction.voided.is_(False),
        )
    ).scalar_one_or_none()


def _any_tx_by_ref(db: Session, ref: str) -> Optional[Transaction]:
    return db.execute(
        select(Transaction).where(
            Transaction.type == TransactionType.expense,
            Transaction.reference_no == ref,
        )
    ).scalar_one_or_none()


def _void_tx(db: Session, tx: Transaction, reason: str) -> None:
    tx.voided = True
    tx.voided_at = _now_utc()
    tx.void_reason = reason
    db.add(tx)


def _void_matching_transactions(db: Session, refs: Iterable[str], reason: str) -> None:
    seen = set()
    for ref in refs:
        if not ref or ref in seen:
            continue
        seen.add(ref)
        tx = _active_tx_by_ref(db, ref)
        if tx:
            _void_tx(db, tx, reason)


def _upsert_transaction_for_expense(
    db: Session, exp: Expense, prev_ref: Optional[str] = None
) -> Transaction:
    """
    Create/update the non-voided transaction for a PAID expense.

    - Uses reference_no if provided; else "EXP-{expense.id}".
    - If reference_no changed, rename the existing tx (no duplicate).
    - If the new ref is already used by a different active tx, raise 409.
    - If only a voided tx exists with the new ref, revive it.
    """
    if exp.id is None:
        db.flush()

    new_ref = _expense_ref(exp)
    tx_date = exp.paid_at.date() if exp.paid_at else exp.expense_date
    tx_desc = (exp.description or exp.vendor_name or "Expense")

    # Reference changed? try to rename existing tx first
    if prev_ref and prev_ref != new_ref:
        conflict = _active_tx_by_ref(db, new_ref)
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"reference_no '{new_ref}' is already used by another active transaction",
            )
        old_tx = _active_tx_by_ref(db, prev_ref)
        if old_tx:
            old_tx.reference_no = new_ref
            old_tx.date = tx_date
            old_tx.description = tx_desc
            old_tx.amount = exp.amount
            old_tx.category_id = exp.category_id
            old_tx.payment_method = _pm_to_enum(exp.payment_method)
            db.add(old_tx)
            return old_tx

    # Existing active tx on (possibly new) ref?
    tx = _active_tx_by_ref(db, new_ref)
    if tx:
        tx.date = tx_date
        tx.description = tx_desc
        tx.amount = exp.amount
        tx.category_id = exp.category_id
        tx.payment_method = _pm_to_enum(exp.payment_method)
        db.add(tx)
        return tx

    # Revive voided tx if present
    voided_tx = _any_tx_by_ref(db, new_ref)
    if voided_tx and voided_tx.voided:
        voided_tx.voided = False
        voided_tx.voided_at = None
        voided_tx.void_reason = None
        voided_tx.date = tx_date
        voided_tx.description = tx_desc
        voided_tx.amount = exp.amount
        voided_tx.category_id = exp.category_id
        voided_tx.payment_method = _pm_to_enum(exp.payment_method)
        db.add(voided_tx)
        return voided_tx

    # Create fresh
    tx = Transaction(
        date=tx_date,
        description=tx_desc,
        amount=exp.amount,  # positive; direction is via type
        type=TransactionType.expense,
        category_id=exp.category_id,
        parishioner_id=None,
        payment_method=_pm_to_enum(exp.payment_method),
        reference_no=new_ref,
    )
    db.add(tx)
    return tx


def _hard_delete_allowed(db: Session) -> bool:
    """Read compliance flag; default to False (locked) if unavailable."""
    try:
        if ComplianceConfig is None:
            return False
        cfg = db.get(ComplianceConfig, 1)
        return bool(cfg and cfg.allow_hard_delete)
    except Exception:
        return False


def _enforce_voids(db: Session) -> bool:
    try:
        if ComplianceConfig is None:
            return True
        cfg = db.get(ComplianceConfig, 1)
        return bool(cfg.enforce_voids) if cfg else True
    except Exception:
        return True


# --- routes ------------------------------------------------------------------
@router.post("/", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def create_expense(payload: ExpenseCreate, db: Session = Depends(get_db)) -> ExpenseOut:
    _ensure_category_exists(db, payload.category_id)

    status_enum = (
        ModelExpenseStatus(payload.status.value)
        if isinstance(payload.status, SchemaExpenseStatus)
        else ModelExpenseStatus.PENDING
    )

    exp = Expense(
        expense_date=payload.expense_date,
        amount=payload.amount,
        category_id=payload.category_id,
        vendor_name=payload.vendor_name,
        description=payload.description,
        status=status_enum,
        due_date=payload.due_date,
        paid_at=payload.paid_at
        if payload.paid_at
        else (_now_utc() if status_enum == ModelExpenseStatus.PAID else None),
        payment_method=payload.payment_method,
        reference_no=payload.reference_no,
    )
    db.add(exp)
    db.flush()  # ensure ID for synthesized ref

    if status_enum == ModelExpenseStatus.PAID:
        try:
            _upsert_transaction_for_expense(db, exp)
        except HTTPException:
            raise
        except IntegrityError:
            raise HTTPException(status_code=409, detail="reference_no already in use")

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="reference_no already in use")

    db.refresh(exp)
    return exp


@router.get("/", response_model=List[ExpenseOut])
def list_expenses(
    db: Session = Depends(get_db),
    q: Optional[str] = Query(None, description="Search vendor/description/reference"),
    status_: Optional[SchemaExpenseStatus] = Query(
        None, alias="status", description="PENDING or PAID"
    ),
    category_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    min_amount: Optional[Decimal] = None,
    max_amount: Optional[Decimal] = None,
    skip: int = 0,
    limit: int = Query(50, le=200),
) -> List[ExpenseOut]:
    conds = []

    if q:
        like = f"%{q}%"
        conds.append(
            or_(
                Expense.vendor_name.ilike(like),
                Expense.description.ilike(like),
                Expense.reference_no.ilike(like),
            )
        )

    if status_ is not None:
        conds.append(Expense.status == ModelExpenseStatus(status_.value))
    if category_id is not None:
        conds.append(Expense.category_id == category_id)
    if date_from is not None:
        conds.append(Expense.expense_date >= date_from)
    if date_to is not None:
        conds.append(Expense.expense_date <= date_to)
    if min_amount is not None:
        conds.append(Expense.amount >= min_amount)
    if max_amount is not None:
        conds.append(Expense.amount <= max_amount)

    stmt = (
        select(Expense)
        .where(and_(*conds))
        .order_by(Expense.expense_date.desc(), Expense.id.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = db.execute(stmt).scalars().all()
    return rows


@router.get("/{expense_id}", response_model=ExpenseOut)
def get_expense(expense_id: int, db: Session = Depends(get_db)) -> ExpenseOut:
    exp = db.get(Expense, expense_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Expense not found")
    return exp


@router.patch("/{expense_id}", response_model=ExpenseOut)
def update_expense(
    expense_id: int, payload: ExpenseUpdate, db: Session = Depends(get_db)
) -> ExpenseOut:
    exp = db.get(Expense, expense_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Expense not found")

    data = payload.model_dump(exclude_unset=True)

    # Capture old state before mutating
    old_status = exp.status
    old_ref = _expense_ref(exp)

    # Validate FK if category_id is being set
    if "category_id" in data:
        _ensure_category_exists(db, data["category_id"])

    # Handle status + paid_at logic
    if "status" in data and data["status"] is not None:
        new_status = data["status"]
        status_enum = (
            ModelExpenseStatus(new_status.value)
            if isinstance(new_status, SchemaExpenseStatus)
            else ModelExpenseStatus(new_status)
        )
        exp.status = status_enum
        if status_enum == ModelExpenseStatus.PAID:
            if "paid_at" not in data or data["paid_at"] is None:
                exp.paid_at = _now_utc()
        else:  # PENDING
            if "paid_at" not in data:
                exp.paid_at = None
        data.pop("status")

    # Apply remaining fields (including explicit None)
    for field, value in data.items():
        setattr(exp, field, value)

    db.add(exp)
    db.flush()

    # If moved PAID -> PENDING, void the linked transaction(s)
    new_ref = _expense_ref(exp)
    if old_status == ModelExpenseStatus.PAID and exp.status == ModelExpenseStatus.PENDING:
        _void_matching_transactions(
            db,
            refs=[old_ref, new_ref],
            reason=f"Expense {exp.id} moved to PENDING",
        )
    else:
        # If PAID (remained PAID or became PAID), upsert/rename tx
        if exp.status == ModelExpenseStatus.PAID:
            try:
                _upsert_transaction_for_expense(db, exp, prev_ref=old_ref)
            except HTTPException:
                raise
            except IntegrityError:
                raise HTTPException(status_code=409, detail="reference_no already in use")

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="reference_no already in use")

    db.refresh(exp)
    return exp


class MarkPaidPayload(ExpenseUpdate):
    """Narrow body for mark_paid; inherits optional payment fields & paid_at."""
    pass


@router.post("/{expense_id}/mark_paid", response_model=ExpenseOut)
def mark_paid(
    expense_id: int,
    payload: MarkPaidPayload | None = None,
    db: Session = Depends(get_db),
) -> ExpenseOut:
    exp = db.get(Expense, expense_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Expense not found")

    old_ref = _expense_ref(exp)

    exp.status = ModelExpenseStatus.PAID
    if payload and payload.paid_at is not None:
        exp.paid_at = payload.paid_at
    else:
        exp.paid_at = _now_utc()

    if payload:
        if payload.payment_method is not None:
            exp.payment_method = payload.payment_method
        if payload.reference_no is not None:
            exp.reference_no = payload.reference_no

    db.add(exp)
    db.flush()

    try:
        _upsert_transaction_for_expense(db, exp, prev_ref=old_ref)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="reference_no already in use")

    db.refresh(exp)
    return exp


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: int, db: Session = Depends(get_db)) -> Response:
    # Gate hard deletes behind compliance flag
    if not _hard_delete_allowed(db):
        raise HTTPException(
            status_code=403,
            detail="Hard delete is disabled by compliance policy. Set the expense to PENDING (which voids any linked transactions) or ask an admin to enable allow_hard_delete.",
        )

    exp = db.get(Expense, expense_id)
    if not exp:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # If we *do* allow hard delete and enforce_voids is on, void any linked tx first
    if _enforce_voids(db):
        ref = _expense_ref(exp)
        _void_matching_transactions(db, refs=[ref], reason=f"Expense {expense_id} deleted")

    db.delete(exp)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
