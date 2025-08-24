from __future__ import annotations
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db import get_db
from app.models.account import Account, AccountType as ModelAccountType
from app.schemas.account import AccountCreate, AccountOut, AccountUpdate

router = APIRouter(prefix="/accounts", tags=["Accounts"])

@router.post("/", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)) -> AccountOut:
    acc = Account(
        name=payload.name,
        type=payload.type,
        institution=payload.institution,
        account_no=payload.account_no,
        currency=payload.currency,
        opening_balance=payload.opening_balance,
        active=payload.active,
    )
    db.add(acc)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Account conflict (unique fields)")
    db.refresh(acc)
    return acc

@router.get("/", response_model=List[AccountOut])
def list_accounts(
    db: Session = Depends(get_db),
    q: Optional[str] = Query(None, description="Search by name/institution/account no."),
    type_: Optional[ModelAccountType] = Query(None, alias="type"),
    active: Optional[bool] = None,
    limit: int = Query(100, le=500),
    skip: int = 0,
) -> List[AccountOut]:
    conds = []
    if q:
        like = f"%{q}%"
        conds.append(or_(Account.name.ilike(like), Account.institution.ilike(like), Account.account_no.ilike(like)))
    if type_ is not None:
        conds.append(Account.type == type_)
    if active is not None:
        conds.append(Account.active == active)

    stmt = select(Account).where(and_(*conds) if conds else True).order_by(Account.name.asc()).offset(skip).limit(limit)
    return db.execute(stmt).scalars().all()

@router.get("/{account_id}", response_model=AccountOut)
def get_account(account_id: int, db: Session = Depends(get_db)) -> AccountOut:
    acc = db.get(Account, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    return acc

@router.patch("/{account_id}", response_model=AccountOut)
def update_account(account_id: int, payload: AccountUpdate, db: Session = Depends(get_db)) -> AccountOut:
    acc = db.get(Account, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(acc, k, v)

    db.add(acc)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Account conflict (unique fields)")
    db.refresh(acc)
    return acc
