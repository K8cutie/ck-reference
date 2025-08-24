from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db

router = APIRouter(prefix="/sigma", tags=["sigma"])

# -------- helpers --------
def _require_tz(dt: Optional[datetime], name: str) -> None:
    if dt is None:
        return
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise HTTPException(status_code=400, detail=f"{name} must be timezone-aware")

def _ensure_defects_table(db: Session) -> None:
    # Create table & indexes if missing, then commit DDL so subsequent INSERTs don’t see a pending txn
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS sigma_defects (
            id UUID PRIMARY KEY,
            process VARCHAR(100) NOT NULL,
            ctq VARCHAR(100),
            category VARCHAR(100) NOT NULL,
            count INTEGER NOT NULL,
            period_start TIMESTAMPTZ NOT NULL,
            period_end   TIMESTAMPTZ NOT NULL,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_sigma_defects_process ON sigma_defects(process)"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_sigma_defects_period_start ON sigma_defects(period_start)"))
    db.commit()

# -------- schemas --------
class SigmaDefectItem(BaseModel):
    category: str
    count: int = Field(ge=0)

class SigmaDefectsBatchCreate(BaseModel):
    process: str
    ctq: Optional[str] = None
    period_start: datetime
    period_end: datetime
    items: List[SigmaDefectItem]
    notes: Optional[str] = None

class SigmaDefectRead(BaseModel):
    id: uuid.UUID
    process: str
    ctq: Optional[str] = None
    category: str
    count: int
    period_start: datetime
    period_end: datetime
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class ParetoItem(BaseModel):
    rank: int
    category: str
    count: int
    percent: float
    cumulative_percent: float

class ParetoResponse(BaseModel):
    process: str
    ctq: Optional[str]
    start: datetime
    end: datetime
    total: int
    limit: int
    truncated: bool
    items: List[ParetoItem]

# -------- endpoints --------
@router.post("/defects", response_model=List[SigmaDefectRead], status_code=status.HTTP_201_CREATED)
def create_defects_batch(payload: SigmaDefectsBatchCreate, db: Session = Depends(get_db)) -> List[SigmaDefectRead]:
    _require_tz(payload.period_start, "period_start")
    _require_tz(payload.period_end, "period_end")
    if payload.period_end < payload.period_start:
        raise HTTPException(status_code=400, detail="period_end must be >= period_start")
    if not payload.items:
        raise HTTPException(status_code=400, detail="items cannot be empty")

    _ensure_defects_table(db)

    created: List[SigmaDefectRead] = []
    try:
        for it in payload.items:
            row = db.execute(text("""
                INSERT INTO sigma_defects
                  (id, process, ctq, category, count, period_start, period_end, notes)
                VALUES
                  (:id, :process, :ctq, :category, :pcount, :pstart, :pend, :notes)
                RETURNING id, process, ctq, category, count, period_start, period_end, notes, created_at, updated_at
            """), {
                "id": uuid.uuid4(),
                "process": payload.process,
                "ctq": payload.ctq,
                "category": it.category,
                "pcount": it.count,            # avoid param name "count"
                "pstart": payload.period_start,
                "pend": payload.period_end,
                "notes": payload.notes,
            }).mappings().first()
            created.append(SigmaDefectRead(**row))  # type: ignore[arg-type]
        db.commit()
    except Exception as e:
        db.rollback()
        # bubble up the real error so you don’t just see “Internal Server Error”
        raise HTTPException(status_code=500, detail=f"defects insert failed: {e}")

    return created

@router.get("/pareto", response_model=ParetoResponse)
def pareto(
    process: str = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...),
    ctq: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ParetoResponse:
    _require_tz(start, "start"); _require_tz(end, "end")
    if end < start:
        raise HTTPException(status_code=400, detail="end must be >= start")

    _ensure_defects_table(db)

    params = {"process": process, "start": start, "end": end, "ctq": ctq}
    where = """
        process = :process
        AND period_end >= :start
        AND period_start <= :end
    """
    if ctq:
        where += " AND ctq = :ctq"

    rows = db.execute(text(f"""
        SELECT category, COALESCE(SUM(count), 0) AS total
        FROM sigma_defects
        WHERE {where}
        GROUP BY category
        ORDER BY total DESC
    """), params).mappings().all()

    totals = [(r["category"], int(r["total"])) for r in rows]
    grand_total = sum(v for _, v in totals)

    if grand_total == 0:
        return ParetoResponse(
            process=process, ctq=ctq, start=start, end=end,
            total=0, limit=limit, truncated=False, items=[]
        )

    items: List[ParetoItem] = []
    top = totals[:limit]
    other = totals[limit:]
    cum = 0.0
    rank = 0

    for cat, cnt in top:
        rank += 1
        pct = (cnt / grand_total) * 100.0
        cum += pct
        items.append(ParetoItem(rank=rank, category=cat, count=cnt, percent=pct, cumulative_percent=cum))

    truncated = len(totals) > limit
    if truncated:
        other_cnt = sum(v for _, v in other)
        pct = (other_cnt / grand_total) * 100.0
        cum += pct
        items.append(ParetoItem(rank=rank + 1, category="Other", count=other_cnt, percent=pct, cumulative_percent=cum))

    return ParetoResponse(
        process=process, ctq=ctq, start=start, end=end,
        total=grand_total, limit=limit, truncated=truncated, items=items
    )
