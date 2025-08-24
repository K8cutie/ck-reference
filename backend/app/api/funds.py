from __future__ import annotations
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db import get_db
from app.models.fund import Fund
from app.schemas.fund import FundCreate, FundOut, FundUpdate

router = APIRouter(prefix="/funds", tags=["Funds"])

@router.post("/", response_model=FundOut, status_code=status.HTTP_201_CREATED)
def create_fund(payload: FundCreate, db: Session = Depends(get_db)) -> FundOut:
    fund = Fund(**payload.model_dump())
    db.add(fund)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Fund conflict (code must be unique if set)")
    db.refresh(fund)
    return fund

@router.get("/", response_model=List[FundOut])
def list_funds(
    db: Session = Depends(get_db),
    q: Optional[str] = Query(None, description="Search by name/code"),
    restricted: Optional[bool] = None,
    limit: int = Query(200, le=500),
    skip: int = 0,
) -> List[FundOut]:
    conds = []
    if q:
        like = f"%{q}%"
        conds.append(or_(Fund.name.ilike(like), Fund.code.ilike(like)))
    if restricted is not None:
        conds.append(Fund.restricted == restricted)

    stmt = select(Fund).where(and_(*conds) if conds else True).order_by(Fund.name.asc()).offset(skip).limit(limit)
    return db.execute(stmt).scalars().all()

@router.get("/{fund_id}", response_model=FundOut)
def get_fund(fund_id: int, db: Session = Depends(get_db)) -> FundOut:
    fund = db.get(Fund, fund_id)
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")
    return fund

@router.patch("/{fund_id}", response_model=FundOut)
def update_fund(fund_id: int, payload: FundUpdate, db: Session = Depends(get_db)) -> FundOut:
    fund = db.get(Fund, fund_id)
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(fund, k, v)

    db.add(fund)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Fund conflict (code must be unique if set)")
    db.refresh(fund)
    return fund
