from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.schemas.gl_accounting import GLAccountCreate, GLAccountUpdate, GLAccountOut
from app.services.gl_accounting import (
    list_gl_accounts,
    create_gl_account,
    update_gl_account,
)

router = APIRouter()  # no prefix; parent will mount under /gl

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/accounts", response_model=List[GLAccountOut])
def api_list_gl_accounts(
    q: Optional[str] = Query(None),
    type: Optional[str] = Query(None, pattern="^(asset|liability|equity|income|expense)$"),
    is_active: Optional[bool] = None,
    is_cash: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    try:
        return list_gl_accounts(db, q=q, type_=type, is_active=is_active, is_cash=is_cash, limit=limit, offset=offset)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GL list failed: {e}")

@router.post("/accounts", response_model=GLAccountOut)
def api_create_gl_account(payload: GLAccountCreate, db: Session = Depends(get_db)):
    try:
        return create_gl_account(
            db,
            code=payload.code,
            name=payload.name,
            type_=payload.type.value if hasattr(payload.type, "value") else payload.type,
            normal_side=payload.normal_side.value if hasattr(payload.normal_side, "value") else payload.normal_side,
            is_cash=payload.is_cash,
            description=payload.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GL create failed: {e}")

@router.patch("/accounts/{account_id}", response_model=GLAccountOut)
def api_update_gl_account(account_id: int, payload: GLAccountUpdate, db: Session = Depends(get_db)):
    try:
        return update_gl_account(
            db,
            account_id,
            code=payload.code,
            name=payload.name,
            type_=payload.type.value if getattr(payload, "type", None) else None,
            normal_side=payload.normal_side.value if getattr(payload, "normal_side", None) else None,
            is_cash=payload.is_cash,
            description=payload.description,
            is_active=payload.is_active,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GL update failed: {e}")
