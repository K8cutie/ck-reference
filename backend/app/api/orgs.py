from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

# Reuse existing deps (RBAC may be dev-bypassed per STATUS.md; we still wire the guard)
from app.api.deps import get_db, require_permission  # type: ignore

router = APIRouter(prefix="/orgs", tags=["Organization"])

# ---------- helpers ----------

def _parse_month(month: Optional[str]) -> (date, date):
    """
    month: 'YYYY-MM' or None -> returns [start, end_exclusive)
    If None, uses the current month (server time).
    """
    if month:
        try:
            y, m = month.split("-")
            start = date(int(y), int(m), 1)
        except Exception:
            raise HTTPException(status_code=400, detail="month must be YYYY-MM")
    else:
        today = date.today()
        start = date(today.year, today.month, 1)
    # next month
    if start.month == 12:
        end = date(start.year + 1, 1, 1)
    else:
        end = date(start.year, start.month + 1, 1)
    return start, end


def _month_bounds(from_month: str, to_month: str) -> (date, date):
    start, _ = _parse_month(from_month)
    end_start, end_excl = _parse_month(to_month)
    # we want inclusive-month range; end_excl is already the first day of the next month after to_month
    return start, end_excl


# ---------- endpoints ----------

@router.get("/{org_id}/kpis")
def org_kpis(
    org_id: int,
    month: Optional[str] = Query(None, description="YYYY-MM; default = current month"),
    db: Session = Depends(get_db),
    _=Depends(require_permission("org:dashboard:view")),
) -> Dict[str, Any]:
    """
    Org-level KPIs for a given month:
    - revenue, expense, net
    - data_freshness (latest transaction date for this org)
    - budget, variance (placeholder: null until budgets are added)
    """
    start, end = _parse_month(month)

    # Use transactions as the fact source (type is an enum; compare via ::text)
    q = text(
        """
        SELECT
            COALESCE(SUM(CASE WHEN t.type::text = 'income'  THEN t.amount ELSE 0 END), 0)::numeric AS revenue,
            COALESCE(SUM(CASE WHEN t.type::text = 'expense' THEN t.amount ELSE 0 END), 0)::numeric AS expense
        FROM transactions t
        WHERE t.org_id = :org_id
          AND t.date >= :start AND t.date < :end
        """
    )
    row = db.execute(q, {"org_id": org_id, "start": start, "end": end}).one()
    revenue = row.revenue or 0
    expense = row.expense or 0
    net = revenue - expense

    # Data freshness = latest transaction date for this org
    q2 = text("SELECT MAX(date) AS latest_date FROM transactions WHERE org_id=:org_id")
    latest = db.execute(q2, {"org_id": org_id}).scalar()

    return {
        "org_id": org_id,
        "month": start.strftime("%Y-%m"),
        "revenue": float(revenue),
        "expense": float(expense),
        "net": float(net),
        "budget": None,
        "variance": None,
        "data_freshness": latest.isoformat() if latest else None,
    }


@router.get("/{org_id}/units/leaderboard")
def org_units_leaderboard(
    org_id: int,
    month: Optional[str] = Query(None, description="YYYY-MM; default = current month"),
    metric: str = Query("revenue", pattern="^(revenue|revenue_growth)$"),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(require_permission("org:dashboard:view")),
) -> Dict[str, Any]:
    """
    Leaderboard of units by metric:
    - revenue: total income this month
    - revenue_growth: (this month - last month) / last month; falls back to 0 if last month is 0
    """
    start, end = _parse_month(month)
    # current month revenue by unit
    q_cur = text(
        """
        SELECT t.unit_id, u.name AS unit_name, u.code AS unit_code,
               COALESCE(SUM(CASE WHEN t.type::text='income' THEN t.amount ELSE 0 END),0)::numeric AS revenue
        FROM transactions t
        JOIN org_units u ON u.id = t.unit_id
        WHERE t.org_id = :org_id AND t.date >= :start AND t.date < :end
        GROUP BY t.unit_id, u.name, u.code
        """
    )
    cur = {int(r.unit_id): {"unit_id": int(r.unit_id), "unit_name": r.unit_name, "unit_code": r.unit_code, "revenue": float(r.revenue)} for r in db.execute(q_cur, {"org_id": org_id, "start": start, "end": end}).all()}

    if metric == "revenue":
        rows = sorted(cur.values(), key=lambda x: x["revenue"], reverse=True)[:limit]
        return {"org_id": org_id, "month": start.strftime("%Y-%m"), "metric": "revenue", "rows": rows}

    # revenue_growth
    # previous month bounds
    prev_end = start
    if start.month == 1:
        prev_start = date(start.year - 1, 12, 1)
    else:
        prev_start = date(start.year, start.month - 1, 1)

    q_prev = text(
        """
        SELECT t.unit_id,
               COALESCE(SUM(CASE WHEN t.type::text='income' THEN t.amount ELSE 0 END),0)::numeric AS revenue
        FROM transactions t
        WHERE t.org_id = :org_id AND t.date >= :start AND t.date < :end
        GROUP BY t.unit_id
        """
    )
    prev = {int(r.unit_id): float(r.revenue) for r in db.execute(q_prev, {"org_id": org_id, "start": prev_start, "end": prev_end}).all()}

    rows = []
    for uid, cur_row in cur.items():
        prev_rev = prev.get(uid, 0.0)
        cur_rev = cur_row["revenue"]
        growth = 0.0
        if prev_rev > 0:
            growth = (cur_rev - prev_rev) / prev_rev
        rows.append({**cur_row, "prev_revenue": prev_rev, "growth": growth})
    rows.sort(key=lambda x: x["growth"], reverse=True)
    rows = rows[:limit]
    return {"org_id": org_id, "month": start.strftime("%Y-%m"), "metric": "revenue_growth", "rows": rows}


@router.get("/{org_id}/compliance/period-locks")
def org_compliance_period_locks(
    org_id: int,
    month: Optional[str] = Query(None, description="YYYY-MM; default = current month"),
    db: Session = Depends(get_db),
    _=Depends(require_permission("org:dashboard:view")),
) -> Dict[str, Any]:
    """
    Report lock coverage for a month:
    - total_units (active)
    - locked_count
    - unlocked_count
    - missing_count (no lock row)
    """
    start, _ = _parse_month(month)

    total_units = db.execute(
        text("SELECT COUNT(*) FROM org_units WHERE org_id=:org_id AND is_active = TRUE"),
        {"org_id": org_id},
    ).scalar() or 0

    locks = db.execute(
        text(
            """
            SELECT unit_id, is_locked
            FROM gl_period_locks
            WHERE org_id = :org_id AND period_month = :period_month
            """
        ),
        {"org_id": org_id, "period_month": start},
    ).all()

    locked = sum(1 for r in locks if r.is_locked)
    unlocked = sum(1 for r in locks if not r.is_locked)
    covered_units = len(set(int(r.unit_id) for r in locks))
    missing = max(total_units - covered_units, 0)

    return {
        "org_id": org_id,
        "month": start.strftime("%Y-%m"),
        "total_units": int(total_units),
        "locked_count": int(locked),
        "unlocked_count": int(unlocked),
        "missing_count": int(missing),
    }


@router.get("/{org_id}/reports/financials")
def org_financials_report_csv(
    org_id: int,
    from_month: str = Query(..., alias="from", description="YYYY-MM"),
    to_month: str = Query(..., alias="to", description="YYYY-MM"),
    db: Session = Depends(get_db),
    _=Depends(require_permission("org:reports:export")),
):
    """
    CSV export of monthly revenue/expense per unit between [from_month, to_month].
    Columns: month, unit_code, revenue, expense, net
    """
    start, end_excl = _month_bounds(from_month, to_month)

    q = text(
        """
        SELECT date_trunc('month', t.date)::date AS month,
               t.unit_id,
               u.code AS unit_code,
               COALESCE(SUM(CASE WHEN t.type::text='income'  THEN t.amount ELSE 0 END),0)::numeric AS revenue,
               COALESCE(SUM(CASE WHEN t.type::text='expense' THEN t.amount ELSE 0 END),0)::numeric AS expense
        FROM transactions t
        JOIN org_units u ON u.id = t.unit_id
        WHERE t.org_id = :org_id AND t.date >= :start AND t.date < :end
        GROUP BY 1,2,3
        ORDER BY 1, 3
        """
    )
    rows = db.execute(q, {"org_id": org_id, "start": start, "end": end_excl}).all()

    def _gen():
        import csv, io
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["month", "unit_code", "revenue", "expense", "net"])
        yield buf.getvalue(); buf.seek(0); buf.truncate(0)
        for r in rows:
            month_str = r.month.strftime("%Y-%m")
            revenue = float(r.revenue or 0)
            expense = float(r.expense or 0)
            net = revenue - expense
            w.writerow([month_str, r.unit_code, f"{revenue:.2f}", f"{expense:.2f}", f"{net:.2f}"])
            yield buf.getvalue(); buf.seek(0); buf.truncate(0)

    filename = f"org_{org_id}_financials_{start:%Y%m}_{(end_excl - timedelta(days=1)):%Y%m}.csv"
    return StreamingResponse(
        _gen(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
