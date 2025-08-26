# app/api/gl_journal.py
from __future__ import annotations

from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.schemas.gl_accounting import JournalEntryCreate, JournalEntryOut
from app.services.gl_accounting import (
    list_journal_entries,
    create_journal_entry,
    post_journal_entry,
    unpost_journal_entry,
    reverse_journal_entry,
)
# RBAC guard
from app.api.rbac import require_permission

router = APIRouter()  # mounted under /gl

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/journal", response_model=List[JournalEntryOut])
def api_list_journal_entries(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    reference_no: Optional[str] = None,
    source_module: Optional[str] = None,
    is_locked: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    try:
        return list_journal_entries(
            db,
            date_from=date_from,
            date_to=date_to,
            reference_no=reference_no,
            source_module=source_module,
            is_locked=is_locked,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"JE list failed: {e}")

@router.post("/journal", response_model=JournalEntryOut)
def api_create_journal_entry(payload: JournalEntryCreate, db: Session = Depends(get_db)):
    try:
        return create_journal_entry(
            db,
            entry_date=payload.entry_date,
            memo=payload.memo,
            currency_code=payload.currency_code,
            reference_no=payload.reference_no,
            source_module=payload.source_module,
            source_id=payload.source_id,
            lines=[l.model_dump() for l in payload.lines],
            created_by_user_id=None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"JE create failed: {e}")

@router.post(
    "/journal/{je_id}/post",
    response_model=JournalEntryOut,
    dependencies=[Depends(require_permission("gl:journal:post"))],
)
def api_post_journal_entry(je_id: int, db: Session = Depends(get_db)):
    try:
        return post_journal_entry(db, je_id, posted_by_user_id=None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"JE post failed: {e}")

@router.post(
    "/journal/{je_id}/unpost",
    response_model=JournalEntryOut,
    dependencies=[Depends(require_permission("gl:journal:unpost"))],
)
def api_unpost_journal_entry(je_id: int, db: Session = Depends(get_db)):
    try:
        return unpost_journal_entry(db, je_id, unposted_by_user_id=None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"JE unpost failed: {e}")

@router.post(
    "/journal/{je_id}/reverse",
    response_model=JournalEntryOut,
    dependencies=[Depends(require_permission("gl:journal:reverse"))],
)
def api_reverse_journal_entry(
    je_id: int,
    as_of: Optional[date] = Query(None, description="Reverse as of this date; defaults to source JE date"),
    db: Session = Depends(get_db),
):
    try:
        return reverse_journal_entry(db, je_id, as_of=as_of, created_by_user_id=None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"JE reverse failed: {e}")
