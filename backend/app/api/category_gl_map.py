# app/api/category_gl_map.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.categories import Category
from app.models.gl_accounting import GLAccount
from app.models.category_gl_map import CategoryGLMap

router = APIRouter(prefix="/categories", tags=["Categories • GL Mapping"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- Schemas ----------

class GLAccountBrief(BaseModel):
    id: int
    code: str
    name: str

class CategoryGLMapOut(BaseModel):
    category_id: int
    debit_account_id: Optional[int] = None
    credit_account_id: Optional[int] = None
    debit_account: Optional[GLAccountBrief] = None
    credit_account: Optional[GLAccountBrief] = None

class CategoryGLMapUpdate(BaseModel):
    debit_account_id: Optional[int] = Field(None, description="GL account id to use on the DEBIT side")
    credit_account_id: Optional[int] = Field(None, description="GL account id to use on the CREDIT side")


# ---------- Helpers ----------

def _brief(a: Optional[GLAccount]) -> Optional[GLAccountBrief]:
    if not a:
        return None
    return GLAccountBrief(id=a.id, code=a.code, name=a.name)

def _load_map_payload(db: Session, category_id: int) -> CategoryGLMapOut:
    m = db.execute(
        select(CategoryGLMap).where(CategoryGLMap.category_id == category_id)
    ).scalars().first()

    debit = db.get(GLAccount, m.debit_account_id) if (m and m.debit_account_id) else None
    credit = db.get(GLAccount, m.credit_account_id) if (m and m.credit_account_id) else None

    return CategoryGLMapOut(
        category_id=category_id,
        debit_account_id=m.debit_account_id if m else None,
        credit_account_id=m.credit_account_id if m else None,
        debit_account=_brief(debit),
        credit_account=_brief(credit),
    )


# ---------- Routes ----------

@router.get("/{category_id}/glmap", response_model=CategoryGLMapOut)
def get_category_gl_map(category_id: int, db: Session = Depends(get_db)):
    cat = db.get(Category, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return _load_map_payload(db, category_id)


@router.patch("/{category_id}/glmap", response_model=CategoryGLMapOut)
def update_category_gl_map(
    category_id: int,
    payload: CategoryGLMapUpdate,
    db: Session = Depends(get_db),
):
    cat = db.get(Category, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    # Validate accounts if provided
    debit = None
    credit = None
    if payload.debit_account_id is not None:
        debit = db.get(GLAccount, payload.debit_account_id)
        if not debit:
            raise HTTPException(status_code=400, detail="Invalid debit_account_id")
    if payload.credit_account_id is not None:
        credit = db.get(GLAccount, payload.credit_account_id)
        if not credit:
            raise HTTPException(status_code=400, detail="Invalid credit_account_id")

    # Upsert mapping row
    m = db.execute(
        select(CategoryGLMap).where(CategoryGLMap.category_id == category_id)
    ).scalars().first()
    if not m:
        m = CategoryGLMap(category_id=category_id)
        db.add(m)

    if payload.debit_account_id is not None:
        m.debit_account_id = payload.debit_account_id
    if payload.credit_account_id is not None:
        m.credit_account_id = payload.credit_account_id

    db.commit()
    # Return hydrated payload with brief account info
    return _load_map_payload(db, category_id)
