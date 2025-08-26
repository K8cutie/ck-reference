# app/api/gl_periods.py
from __future__ import annotations

from datetime import date
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db import SessionLocal
from app.schemas.gl_accounting import JournalEntryOut
from app.services.gl_accounting import (
    list_gl_accounts,
    close_period,
    reopen_period,
    reclose_period,
)

router = APIRouter()  # mounted under /gl

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------------
# Single-period endpoints
# -------------------------

@router.post("/close/{year}-{month}", response_model=JournalEntryOut)
def api_close_period(
    year: int,
    month: int,
    equity_account_id: int = Query(..., description="Equity account to receive Net Income/Loss"),
    note: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    try:
        return close_period(db, year, month, equity_account_id=equity_account_id, note=note, created_by_user_id=None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Close period failed: {e}")

@router.post("/reopen/{year}-{month}")
def api_reopen_period(
    year: int,
    month: int,
    note: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    try:
        return reopen_period(db, year, month, note=note)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reopen period failed: {e}")

@router.post("/reclose/{year}-{month}", response_model=JournalEntryOut)
def api_reclose_period(
    year: int,
    month: int,
    equity_account_id: Optional[int] = Query(None, description="If omitted, uses the first EQUITY account"),
    note: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    try:
        eid = int(equity_account_id) if equity_account_id is not None else None
        if not eid:
            eq = list_gl_accounts(db, type_="equity", limit=1, offset=0)
            if not eq:
                raise ValueError("No EQUITY account found; provide equity_account_id.")
            eid = int(eq[0].id)
        return reclose_period(db, year, month, equity_account_id=eid, note=note or "reclosed", created_by_user_id=None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reclose failed: {e}")

# -------------------------
# Range endpoints (inclusive)
# -------------------------

def _parse_range(start: str, end: str) -> tuple[int, int, int, int]:
    try:
        s_year, s_month = [int(x) for x in start.split("-", 1)]
        e_year, e_month = [int(x) for x in end.split("-", 1)]
    except Exception:
        raise HTTPException(status_code=400, detail="start/end must be YYYY-MM")
    if (e_year, e_month) < (s_year, s_month):
        raise HTTPException(status_code=400, detail="end must be >= start")
    return s_year, s_month, e_year, e_month

@router.post("/reclose-range/{start}/{end}")
def api_reclose_range(
    start: str,
    end: str,
    equity_account_id: Optional[int] = Query(None),
    note: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    try:
        s_year, s_month, e_year, e_month = _parse_range(start, end)
        eid = int(equity_account_id) if equity_account_id is not None else None
        if not eid:
            eq = list_gl_accounts(db, type_="equity", limit=1, offset=0)
            if not eq:
                raise HTTPException(status_code=400, detail="No EQUITY account found; provide equity_account_id.")
            eid = int(eq[0].id)

        results: List[Dict[str, Any]] = []
        y, m = s_year, s_month
        while (y < e_year) or (y == e_year and m <= e_month):
            period = f"{y:04d}-{m:02d}"
            try:
                je = reclose_period(db, y, m, equity_account_id=eid, note=note or "reclosed", created_by_user_id=None)
                results.append({"period": period, "ok": True, "je_id": getattr(je, "id", None)})
            except ValueError as ve:
                results.append({"period": period, "ok": False, "error": str(ve)})
            except Exception as ex:
                results.append({"period": period, "ok": False, "error": f"{ex}"})
            if m == 12: y += 1; m = 1
            else: m += 1

        return {"start": start, "end": end, "equity_account_id": eid, "note": note or "reclosed", "results": results}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reclose-range failed: {e}")


@router.post("/reopen-range/{start}/{end}")
def api_reopen_range(
    start: str,
    end: str,
    note: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    try:
        s_year, s_month, e_year, e_month = _parse_range(start, end)
        results: List[Dict[str, Any]] = []

        y, m = s_year, s_month
        while (y < e_year) or (y == e_year and m <= e_month):
            period = f"{y:04d}-{m:02d}"
            try:
                out = reopen_period(db, y, m, note=note or "reopened")
                results.append({"period": period, "ok": True, "result": out})
            except Exception as ex:
                results.append({"period": period, "ok": False, "error": f"{ex}"})
            if m == 12: y += 1; m = 1
            else: m += 1

        return {"start": start, "end": end, "note": note or "reopened", "results": results}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reopen-range failed: {e}")


@router.post("/close-range/{start}/{end}")
def api_close_range(
    start: str,
    end: str,
    equity_account_id: Optional[int] = Query(None, description="If omitted, uses the first EQUITY account"),
    note: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    try:
        s_year, s_month, e_year, e_month = _parse_range(start, end)
        eid = int(equity_account_id) if equity_account_id is not None else None
        if not eid:
            eq = list_gl_accounts(db, type_="equity", limit=1, offset=0)
            if not eq:
                raise HTTPException(status_code=400, detail="No EQUITY account found; provide equity_account_id.")
            eid = int(eq[0].id)

        results: List[Dict[str, Any]] = []
        y, m = s_year, s_month
        while (y < e_year) or (y == e_year and m <= e_month):
            period = f"{y:04d}-{m:02d}"
            try:
                je = close_period(db, y, m, equity_account_id=eid, note=note, created_by_user_id=None)
                results.append({"period": period, "ok": True, "je_id": getattr(je, "id", None)})
            except ValueError as ve:
                results.append({"period": period, "ok": False, "error": str(ve)})
            except Exception as ex:
                results.append({"period": period, "ok": False, "error": f"{ex}"})
            if m == 12: y += 1; m = 1
            else: m += 1

        return {"start": start, "end": end, "equity_account_id": eid, "note": note, "results": results}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Close-range failed: {e}")


# -------------------------
# Locks status (unchanged)
# -------------------------

@router.get("/locks/status")
def api_locks_status(
    from_: str = Query(..., alias="from", description="Start period YYYY-MM"),
    to_: str   = Query(..., alias="to",   description="End period YYYY-MM"),
    db: Session = Depends(get_db),
):
    try:
        try:
            s_year, s_month = [int(x) for x in from_.split("-", 1)]
            e_year, e_month = [int(x) for x in to_.split("-", 1)]
        except Exception:
            raise HTTPException(status_code=400, detail="'from' and 'to' must be YYYY-MM")
        if (e_year, e_month) < (s_year, s_month):
            raise HTTPException(status_code=400, detail="'to' must be >= 'from'")

        results: List[Dict[str, Any]] = []
        y, m = s_year, s_month
        while (y < e_year) or (y == e_year and m <= e_month):
            period = f"{y:04d}-{m:02d}"
            first = date(y, m, 1)
            row = db.execute(
                text("SELECT is_locked, note FROM gl_period_locks WHERE period_month = :pm LIMIT 1"),
                {"pm": first},
            ).first()
            is_locked = bool(row[0]) if row else False
            note = row[1] if row else None
            ref = f"CLOSE-{y:04d}{m:02d}"
            row2 = db.execute(
                text("SELECT id FROM journal_entries WHERE reference_no = :ref AND is_locked = TRUE ORDER BY id DESC LIMIT 1"),
                {"ref": ref},
            ).first()
            closed_je_id = int(row2[0]) if row2 else None
            results.append({"period": period, "is_locked": is_locked, "note": note, "closed_ref": ref, "closed_je_id": closed_je_id})
            if m == 12: y += 1; m = 1
            else: m += 1

        return {"from": from_, "to": to_, "results": results}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Locks status failed: {e}")
