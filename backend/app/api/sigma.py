from __future__ import annotations

import io
import uuid
from math import exp
from typing import List, Optional, Tuple

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt


router = APIRouter(prefix="/sigma", tags=["Six Sigma"])


# ----------------- Pydantic Schemas -----------------

class SigmaLogCreate(BaseModel):
    process: str = Field(..., max_length=100)
    ctq: Optional[str] = Field(None, max_length=100)
    period_start: datetime
    period_end: datetime
    units: int = Field(..., ge=0)
    opportunities_per_unit: int = Field(..., ge=1)
    defects: int = Field(..., ge=0)
    notes: Optional[str] = None


class SigmaLogRead(BaseModel):
    id: uuid.UUID
    process: str
    ctq: Optional[str]
    period_start: datetime
    period_end: datetime
    units: int
    opportunities_per_unit: int
    defects: int
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class DefectItem(BaseModel):
    category: str = Field(..., max_length=100)
    count: int = Field(..., ge=0)


class DefectsBatchCreate(BaseModel):
    process: str = Field(..., max_length=100)
    ctq: Optional[str] = Field(None, max_length=100)
    period_start: datetime
    period_end: datetime
    items: List[DefectItem]
    notes: Optional[str] = None


class SigmaDefectRead(BaseModel):
    id: uuid.UUID
    process: str
    ctq: Optional[str]
    category: str
    count: int
    period_start: datetime
    period_end: datetime
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class SummaryRead(BaseModel):
    process: str
    from_at: datetime
    to_at: datetime
    units: int
    opportunities: int
    defects: int
    dpu: float
    dpmo: float
    fpy: float
    sigma_short: float
    sigma_long: float


class PChartPoint(BaseModel):
    date: datetime
    opportunities: int
    defects: int
    p_hat: float
    ucl: float
    lcl: float


class PChartRead(BaseModel):
    process: str
    p_bar: float
    points: List[PChartPoint]


class ParetoItem(BaseModel):
    category: str
    count: int
    pct: float
    cum_pct: float


class ParetoRead(BaseModel):
    process: str
    ctq: Optional[str]
    start: datetime
    end: datetime
    total: int
    limit: int
    truncated: bool
    items: List[ParetoItem]


# ----------------- Helpers -----------------

def _tzaware(d: datetime) -> datetime:
    if d.tzinfo is None or d.tzinfo.utcoffset(d) is None:
        raise HTTPException(status_code=400, detail="Datetime must be timezone-aware")
    return d


def _inv_norm_cdf(p: float) -> float:
    """Acklam's approximation for the inverse CDF of the standard normal."""
    # bounds
    if p <= 0.0:
        return float("-inf")
    if p >= 1.0:
        return float("inf")

    # Coefficients in rational approximations
    a = [ -3.969683028665376e+01,  2.209460984245205e+02,
          -2.759285104469687e+02,  1.383577518672690e+02,
          -3.066479806614716e+01,  2.506628277459239e+00 ]
    b = [ -5.447609879822406e+01,  1.615858368580409e+02,
          -1.556989798598866e+02,  6.680131188771972e+01,
          -1.328068155288572e+01 ]
    c = [ -7.784894002430293e-03, -3.223964580411365e-01,
          -2.400758277161838e+00, -2.549732539343734e+00,
           4.374664141464968e+00,  2.938163982698783e+00 ]
    d = [  7.784695709041462e-03,  3.224671290700398e-01,
           2.445134137142996e+00,  3.754408661907416e+00 ]

    plow  = 0.02425
    phigh = 1 - plow

    if p < plow:
        q = ( -2.0 * (p)**0.5 )  # cheap start
        q = ( ( ( (c[0]*p + c[1])*p + c[2])*p + c[3])*p + c[4])*p + c[5]
        r = ( ( (d[0]*p + d[1])*p + d[2])*p + d[3] )
        return q / r
    if p > phigh:
        q = 1 - p
        q = ( ( ( (c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]
        r = ( ( (d[0]*q + d[1])*q + d[2])*q + d[3] )
        return -q / r

    q = p - 0.5
    r = q*q
    num = ( ( ( (a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5]
    den = ( ( ( (b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4]) * r + 1.0
    return q * num / den


def _sigma_from_dpu(dpu: float) -> Tuple[float, float]:
    """
    Use Poisson FPY ≈ e^{-DPU}; sigma_short = N^{-1}(FPY); sigma_long = sigma_short + 1.5
    """
    fpy = exp(-dpu)
    # clamp to (0,1) to avoid infs
    fpy = max(min(fpy, 1 - 1e-12), 1e-12)
    z_short = _inv_norm_cdf(fpy)
    return (round(z_short, 3), round(z_short + 1.5, 3))


def _content_disposition(filename: str) -> dict:
    return {"Content-Disposition": f'attachment; filename="{filename}"'}


# ----------------- Endpoints -----------------

@router.post("/logs", response_model=SigmaLogRead, status_code=status.HTTP_201_CREATED)
def create_log(payload: SigmaLogCreate, db: Session = Depends(get_db)) -> SigmaLogRead:
    ps = _tzaware(payload.period_start).astimezone(timezone.utc)
    pe = _tzaware(payload.period_end).astimezone(timezone.utc)
    if pe < ps:
        raise HTTPException(status_code=400, detail="period_end must be >= period_start")

    new_id = str(uuid.uuid4())
    r = db.execute(
        text(
            """
            INSERT INTO sigma_logs
              (id, process, ctq, period_start, period_end, units, opportunities_per_unit, defects, notes)
            VALUES
              (:id, :process, :ctq, :ps, :pe, :units, :opu, :defects, :notes)
            RETURNING id, process, ctq, period_start, period_end, units, opportunities_per_unit, defects, notes, created_at, updated_at
            """
        ),
        {
            "id": new_id,
            "process": payload.process,
            "ctq": payload.ctq,
            "ps": ps,
            "pe": pe,
            "units": payload.units,
            "opu": payload.opportunities_per_unit,
            "defects": payload.defects,
            "notes": payload.notes,
        },
    )
    row = r.first()
    db.commit()
    return SigmaLogRead(**dict(row._mapping))


@router.get("/summary", response_model=SummaryRead)
def summary(
    process: str = Query(...),
    start: datetime = Query(..., description="ISO datetime with tz"),
    end: datetime = Query(..., description="ISO datetime with tz"),
    db: Session = Depends(get_db),
):
    s = _tzaware(start).astimezone(timezone.utc)
    e = _tzaware(end).astimezone(timezone.utc)

    # sum across overlapping runs
    q = db.execute(
        text(
            """
            SELECT
              COALESCE(SUM(units), 0) AS units,
              COALESCE(SUM(units * opportunities_per_unit), 0) AS opportunities,
              COALESCE(SUM(defects), 0) AS defects
            FROM sigma_logs
            WHERE process = :process
              AND period_end   >= :start
              AND period_start <= :end
            """
        ),
        {"process": process, "start": s, "end": e},
    ).first()

    units = int(q.units or 0)
    opportunities = int(q.opportunities or 0)
    defects = int(q.defects or 0)

    dpu = float(defects) / float(units) if units > 0 else 0.0
    dpmo = (float(defects) / float(opportunities) * 1_000_000.0) if opportunities > 0 else 0.0
    fpy = exp(-dpu)  # Poisson approx

    sigma_short, sigma_long = _sigma_from_dpu(dpu)

    return SummaryRead(
        process=process,
        from_at=start,
        to_at=end,
        units=units,
        opportunities=opportunities,
        defects=defects,
        dpu=round(dpu, 6),
        dpmo=round(dpmo, 2),
        fpy=round(fpy, 6),
        sigma_short=sigma_short,
        sigma_long=sigma_long,
    )


@router.get("/control-chart", response_model=PChartRead)
def p_chart_json(
    process: str = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...),
    tz: str = Query("UTC", description="IANA TZ like Asia/Manila"),
    db: Session = Depends(get_db),
):
    s = _tzaware(start).astimezone(timezone.utc)
    e = _tzaware(end).astimezone(timezone.utc)

    rows = db.execute(
        text(
            """
            SELECT period_start, units, opportunities_per_unit, defects
            FROM sigma_logs
            WHERE process = :process
              AND period_end   >= :start
              AND period_start <= :end
            ORDER BY period_start ASC
            """
        ),
        {"process": process, "start": s, "end": e},
    ).all()

    if not rows:
        return PChartRead(process=process, p_bar=0.0, points=[])

    total_def = 0
    total_opp = 0
    pts: List[PChartPoint] = []
    tzinfo = ZoneInfo(tz)

    for r in rows:
        opp = int(r.units) * int(r.opportunities_per_unit)
        d = int(r.defects)
        total_def += d
        total_opp += opp

        p_hat = (d / opp) if opp > 0 else 0.0
        pts.append(PChartPoint(
            date=r.period_start.astimezone(tzinfo),
            opportunities=opp,
            defects=d,
            p_hat=round(p_hat, 6),
            ucl=0.0,  # placeholders; set after p_bar known
            lcl=0.0,
        ))

    p_bar = (total_def / total_opp) if total_opp > 0 else 0.0

    # control limits per point: p̄ ± 3 * sqrt(p̄(1-p̄)/n)
    new_pts: List[PChartPoint] = []
    for p in pts:
        n = max(p.opportunities, 1)
        import math
        se = math.sqrt(max(p_bar * (1 - p_bar) / n, 0.0))
        ucl = min(p_bar + 3 * se, 1.0)
        lcl = max(p_bar - 3 * se, 0.0)
        new_pts.append(PChartPoint(
            date=p.date, opportunities=p.opportunities, defects=p.defects,
            p_hat=p.p_hat, ucl=round(ucl, 6), lcl=round(lcl, 6)
        ))

    return PChartRead(process=process, p_bar=round(p_bar, 6), points=new_pts)


@router.get("/control-chart.png")
def p_chart_png(
    process: str = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...),
    tz: str = Query("UTC"),
    db: Session = Depends(get_db),
):
    data = p_chart_json(process, start, end, tz, db)
    fig = plt.figure(figsize=(8, 4.5))
    xs = [pt.date for pt in data.points]
    ys = [pt.p_hat for pt in data.points]
    ucls = [pt.ucl for pt in data.points]
    lcls = [pt.lcl for pt in data.points]

    plt.plot(xs, ys, marker="o", label="p̂")
    if xs:
        plt.plot(xs, ucls, linestyle="--", label="UCL")
        plt.plot(xs, lcls, linestyle="--", label="LCL")
        plt.axhline(y=data.p_bar, linestyle=":", label="p̄")

    plt.title(f"p-Chart: {process}")
    plt.xlabel("Run start")
    plt.ylabel("Defect proportion")
    plt.legend(loc="best")
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    return Response(content=buf.getvalue(), media_type="image/png",
                    headers=_content_disposition("pchart.png"))


@router.post("/defects", response_model=List[SigmaDefectRead], status_code=status.HTTP_201_CREATED)
def create_defects_batch(payload: DefectsBatchCreate, db: Session = Depends(get_db)) -> List[SigmaDefectRead]:
    ps = _tzaware(payload.period_start).astimezone(timezone.utc)
    pe = _tzaware(payload.period_end).astimezone(timezone.utc)
    if pe < ps:
        raise HTTPException(status_code=400, detail="period_end must be >= period_start")
    if not payload.items:
        return []

    inserted: List[SigmaDefectRead] = []
    for it in payload.items:
        new_id = str(uuid.uuid4())
        row = db.execute(
            text(
                """
                INSERT INTO sigma_defects
                  (id, process, ctq, category, count, period_start, period_end, notes)
                VALUES
                  (:id, :process, :ctq, :category, :count, :ps, :pe, :notes)
                RETURNING id, process, ctq, category, count, period_start, period_end, notes, created_at, updated_at
                """
            ),
            {
                "id": new_id,
                "process": payload.process,
                "ctq": payload.ctq,
                "category": it.category,
                "count": it.count,
                "ps": ps,
                "pe": pe,
                "notes": payload.notes,
            },
        ).first()
        inserted.append(SigmaDefectRead(**dict(row._mapping)))

    db.commit()
    return inserted


@router.get("/defects", response_model=List[SigmaDefectRead])
def list_defects(
    process: str = Query(...),
    ctq: Optional[str] = Query(None),
    start: datetime = Query(...),
    end: datetime = Query(...),
    db: Session = Depends(get_db),
):
    s = _tzaware(start).astimezone(timezone.utc)
    e = _tzaware(end).astimezone(timezone.utc)

    where = ["process = :process", "period_end >= :start", "period_start <= :end"]
    params = {"process": process, "start": s, "end": e}
    if ctq is not None:
        where.append("ctq = :ctq")
        params["ctq"] = ctq

    rows = db.execute(
        text(
            f"""
            SELECT id, process, ctq, category, count, period_start, period_end, notes, created_at, updated_at
            FROM sigma_defects
            WHERE {' AND '.join(where)}
            ORDER BY period_start ASC, category ASC
            """
        ),
        params,
    ).all()
    return [SigmaDefectRead(**dict(r._mapping)) for r in rows]


@router.get("/pareto", response_model=ParetoRead)
def pareto_json(
    process: str = Query(...),
    ctq: Optional[str] = Query(None),
    start: datetime = Query(...),
    end: datetime = Query(...),
    limit: int = Query(5, ge=1, le=50),
    db: Session = Depends(get_db),
):
    s = _tzaware(start).astimezone(timezone.utc)
    e = _tzaware(end).astimezone(timezone.utc)

    where = ["process = :process", "period_end >= :start", "period_start <= :end"]
    params = {"process": process, "start": s, "end": e}
    if ctq is not None:
        where.append("ctq = :ctq")
        params["ctq"] = ctq

    rows = db.execute(
        text(
            f"""
            SELECT category, COALESCE(SUM(count), 0) AS total
            FROM sigma_defects
            WHERE {' AND '.join(where)}
            GROUP BY category
            ORDER BY total DESC, category ASC
            """
        ),
        params,
    ).all()

    totals = [(r.category, int(r.total)) for r in rows]
    grand = sum(c for _, c in totals)

    if grand == 0:
        return ParetoRead(
            process=process, ctq=ctq, start=start, end=end,
            total=0, limit=limit, truncated=False, items=[]
        )

    top = totals[:limit]
    other_count = sum(c for _, c in totals[limit:])
    items: List[ParetoItem] = []

    running = 0
    for cat, cnt in top:
        running += cnt
        items.append(ParetoItem(
            category=cat,
            count=cnt,
            pct=round(cnt / grand, 6),
            cum_pct=round(running / grand, 6),
        ))

    truncated = len(totals) > limit
    if truncated and other_count > 0:
        running += other_count
        items.append(ParetoItem(
            category="Other",
            count=other_count,
            pct=round(other_count / grand, 6),
            cum_pct=round(running / grand, 6),
        ))

    return ParetoRead(
        process=process, ctq=ctq, start=start, end=end,
        total=grand, limit=limit, truncated=truncated, items=items
    )


@router.get("/pareto.csv")
def pareto_csv(
    process: str = Query(...),
    ctq: Optional[str] = Query(None),
    start: datetime = Query(...),
    end: datetime = Query(...),
    limit: int = Query(5, ge=1, le=50),
    db: Session = Depends(get_db),
):
    data = pareto_json(process, ctq, start, end, limit, db)
    lines = ["category,count,pct,cum_pct"]
    for it in data.items:
        lines.append(f"{it.category},{it.count},{it.pct},{it.cum_pct}")
    csv_bytes = ("\n".join(lines)).encode("utf-8")
    return Response(content=csv_bytes, media_type="text/csv",
                    headers=_content_disposition("pareto.csv"))


@router.get("/pareto.png")
def pareto_png(
    process: str = Query(...),
    ctq: Optional[str] = Query(None),
    start: datetime = Query(...),
    end: datetime = Query(...),
    limit: int = Query(5, ge=1, le=50),
    db: Session = Depends(get_db),
):
    data = pareto_json(process, ctq, start, end, limit, db)

    fig = plt.figure(figsize=(7, 4))
    cats = [it.category for it in data.items]
    counts = [it.count for it in data.items]
    cum = [it.cum_pct for it in data.items]
    xs = list(range(len(cats)))

    plt.bar(xs, counts, label="Count")
    plt.plot(xs, cum, marker="o", linestyle="--", label="Cum %")
    plt.xticks(xs, cats, rotation=30, ha="right")
    plt.title(f"Pareto: {process}" + (f" · {ctq}" if ctq else ""))
    plt.ylabel("Count")
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    return Response(content=buf.getvalue(), media_type="image/png",
                    headers=_content_disposition("pareto.png"))
