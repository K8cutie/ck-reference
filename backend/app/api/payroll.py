# backend/app/api/payroll.py
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# NEW: for reflection fallback (idempotent JE backfill)
import sqlalchemy as sa

# Response for HTML endpoint
from fastapi.responses import HTMLResponse

# DB session dependency (project exposes get_db either in app.db.session or app.db)
try:
    from app.db.session import get_db as _get_db  # preferred if present
except Exception:  # pragma: no cover
    from app.db import get_db as _get_db

# Payroll models
from app.models.payroll import Employee, PayrollPeriod, PayrollRun, Payslip

# GL services (same ones your /gl/journal API uses)
from app.services.gl_accounting import (
    create_journal_entry,
    post_journal_entry,
)

# Optional: fetch JE details when returning idempotent response
try:
    from app.models.gl_journal import JournalEntry  # type: ignore
except Exception:  # pragma: no cover
    JournalEntry = None  # type: ignore

router = APIRouter(prefix="/payroll", tags=["payroll"])

# ----------------------------- helpers ----------------------------- #

def _employee_out(emp: Employee) -> Dict[str, Any]:
    return {
        "id": emp.id,
        "code": emp.code,
        "first_name": emp.first_name,
        "last_name": emp.last_name,
        "active": emp.active,
        "pay_type": emp.pay_type,
        "monthly_rate": emp.monthly_rate,
        "daily_rate": emp.daily_rate,
        "hourly_rate": emp.hourly_rate,
        "tax_status": emp.tax_status,
        "sss_no": emp.sss_no,
        "philhealth_no": emp.philhealth_no,
        "pagibig_no": emp.pagibig_no,
        "tin": emp.tin,
        "hire_date": emp.hire_date,
        "termination_date": emp.termination_date,
        "meta": emp.meta or {},
        "created_at": emp.created_at,
    }

def _period_out(p: PayrollPeriod) -> Dict[str, Any]:
    return {
        "id": p.id,
        "period_key": p.period_key,
        "start_date": p.start_date,
        "end_date": p.end_date,
        "pay_date": p.pay_date,
        "status": p.status,
        "meta": p.meta or {},
    }

def _run_out(r: PayrollRun) -> Dict[str, Any]:
    return {
        "id": r.id,
        "period_id": r.period_id,
        "run_no": r.run_no,
        "status": r.status,
        "posted_at": r.posted_at,
        "reference_no": r.reference_no,
        "notes": r.notes,
        "meta": r.meta or {},
        "created_at": r.created_at,
    }

def _payslip_out(s: Payslip) -> Dict[str, Any]:
    return {
        "id": s.id,
        "run_id": s.run_id,
        "employee_id": s.employee_id,
        "gross_pay": s.gross_pay,
        "total_deductions": s.total_deductions,
        "net_pay": s.net_pay,
        "snapshot_json": s.snapshot_json or {},
        "reference_no": s.reference_no,
        "html": s.html,
        "created_at": s.created_at,
    }

# ----------------------------- existing endpoints ----------------------------- #

class EmployeeCreate(BaseModel):
    code: str
    first_name: str
    last_name: str
    active: bool = True
    pay_type: str
    monthly_rate: Optional[Decimal] = None
    daily_rate: Optional[Decimal] = None
    hourly_rate: Optional[Decimal] = None
    tax_status: Optional[str] = None
    sss_no: Optional[str] = None
    philhealth_no: Optional[str] = None
    pagibig_no: Optional[str] = None
    tin: Optional[str] = None
    hire_date: Optional[date] = None
    termination_date: Optional[date] = None
    meta: Dict[str, Any] = {}

@router.post("/employees")
def api_create_employee(payload: EmployeeCreate, db: Session = Depends(_get_db)):
    emp = Employee(**payload.model_dump())
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return _employee_out(emp)

class PayrollPeriodCreate(BaseModel):
    period_key: str
    start_date: date
    end_date: date
    pay_date: date
    status: str = "draft"
    meta: Dict[str, Any] = {}

@router.post("/periods")
def api_create_period(payload: PayrollPeriodCreate, db: Session = Depends(_get_db)):
    exists = db.query(PayrollPeriod).filter(PayrollPeriod.period_key == payload.period_key).first()
    if exists:
        return _period_out(exists)
    p = PayrollPeriod(**payload.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return _period_out(p)

class PayrollRunCreate(BaseModel):
    period_id: UUID
    notes: Optional[str] = None

@router.post("/runs")
def api_create_run(payload: PayrollRunCreate, db: Session = Depends(_get_db)):
    period = db.get(PayrollPeriod, payload.period_id)
    if not period:
        raise HTTPException(status_code=404, detail="PayrollPeriod not found")
    run = PayrollRun(period_id=payload.period_id, notes=payload.notes, status="draft", meta={})
    db.add(run)
    db.commit()
    db.refresh(run)
    return _run_out(run)

from app.services.payroll import compute_run_basic  # noqa: E402

@router.post("/runs/{run_id}/compute-basic")
def api_compute_run_basic(run_id: UUID, db: Session = Depends(_get_db)):
    run = db.get(PayrollRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="PayrollRun not found")
    res = compute_run_basic(db, run_id)
    return {"run_id": str(run_id), **res}

@router.get("/payslips")
def api_list_payslips(run_id: UUID = Query(...), db: Session = Depends(_get_db)):
    slips = (
        db.query(Payslip)
        .filter(Payslip.run_id == run_id)
        .order_by(Payslip.created_at.asc())
        .all()
    )
    return [_payslip_out(s) for s in slips]

# ----------------------------- NEW: post run → GL (idempotent + robust backfill) ----------------------------- #

class PostRunToGLIn(BaseModel):
    debit_account_id: int = Field(..., description="GL account id for expense (debit)")
    credit_account_id: int = Field(..., description="GL account id for cash/payable (credit)")
    memo: Optional[str] = Field(None, description="Optional journal memo")
    currency_code: str = Field("PHP", description="Currency code for the JE (default PHP)")
    entry_date: Optional[date] = Field(None, description="Posting date; defaults to pay_date or period end")

def _je_info(db: Session, je_id: Optional[int], reference_no: Optional[str]) -> Dict[str, Any]:
    if not je_id:
        return {"id": None, "reference_no": reference_no, "is_locked": True}
    if JournalEntry is None:
        return {"id": je_id, "reference_no": reference_no, "is_locked": True}
    je = db.get(JournalEntry, je_id)
    if not je:
        return {"id": je_id, "reference_no": reference_no, "is_locked": True}
    return {
        "id": getattr(je, "id", je_id),
        "entry_no": getattr(je, "entry_no", None),
        "entry_date": getattr(je, "entry_date", None),
        "reference_no": getattr(je, "reference_no", reference_no),
        "is_locked": getattr(je, "is_locked", True),
    }

def _reflective_find_je_id_by_ref(db: Session, ref: str) -> Optional[int]:
    try:
        meta = sa.MetaData()
        meta.reflect(bind=db.bind)
        for tname, table in meta.tables.items():
            lname = tname.lower()
            if "journal" not in lname:
                continue
            cols = {c.lower() for c in table.c.keys()}
            if "reference_no" in cols and "id" in cols:
                stmt = sa.select(table.c.id).where(table.c.reference_no == ref).limit(1)
                row = db.execute(stmt).first()
                if row and row[0]:
                    return int(row[0])
    except Exception:
        pass
    return None

def _backfill_run_je_id(db: Session, run: PayrollRun) -> Optional[int]:
    if not run.reference_no:
        return None
    if JournalEntry is not None:
        try:
            has_source = all(hasattr(JournalEntry, attr) for attr in ("source_module", "source_id"))
            if has_source:
                je = (
                    db.query(JournalEntry)
                    .filter(
                        getattr(JournalEntry, "source_module") == "payroll",
                        getattr(JournalEntry, "source_id") == str(run.id),
                    )
                    .order_by(getattr(JournalEntry, "id"))
                    .first()
                )
                if je:
                    run.meta = dict(run.meta or {})
                    run.meta["gl_journal_id"] = int(getattr(je, "id"))
                    db.commit()
                    return run.meta["gl_journal_id"]
            if hasattr(JournalEntry, "reference_no"):
                je = (
                    db.query(JournalEntry)
                    .filter(getattr(JournalEntry, "reference_no") == run.reference_no)
                    .order_by(getattr(JournalEntry, "id"))
                    .first()
                )
                if je:
                    run.meta = dict(run.meta or {})
                    run.meta["gl_journal_id"] = int(getattr(je, "id"))
                    db.commit()
                    return run.meta["gl_journal_id"]
        except Exception:
            pass
    je_id = _reflective_find_je_id_by_ref(db, run.reference_no)
    if je_id:
        run.meta = dict(run.meta or {})
        run.meta["gl_journal_id"] = je_id
        db.commit()
        return je_id
    return None

@router.post("/runs/{run_id}/post")
def api_post_run_to_gl(
    run_id: UUID,
    payload: PostRunToGLIn = Body(...),
    db: Session = Depends(_get_db),
):
    run = db.get(PayrollRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="PayrollRun not found")

    period = db.get(PayrollPeriod, run.period_id)
    if not period:
        raise HTTPException(status_code=400, detail="PayrollPeriod missing for run")

    if run.status == "posted":
        je_id = (run.meta or {}).get("gl_journal_id")
        if not je_id:
            je_id = _backfill_run_je_id(db, run)
        return {
            "already_posted": True,
            "run": _run_out(run),
            "journal_entry": _je_info(db, je_id, run.reference_no),
            "total_gross": None,
        }

    slips: List[Payslip] = db.query(Payslip).filter(Payslip.run_id == run.id).all()
    if not slips:
        raise HTTPException(status_code=400, detail="No payslips to post for this run (compute first)")

    total_gross = sum(Decimal(s.gross_pay or 0) for s in slips)
    total_gross = Decimal(total_gross).quantize(Decimal("0.01"))
    if total_gross <= 0:
        raise HTTPException(status_code=400, detail="Nothing to post (gross total is 0)")

    lines = [
        {
            "account_id": int(payload.debit_account_id),
            "description": f"Payroll gross – {period.period_key}",
            "debit": float(total_gross),
            "credit": 0.0,
        },
        {
            "account_id": int(payload.credit_account_id),
            "description": f"Payroll gross – {period.period_key}",
            "debit": 0.0,
            "credit": float(total_gross),
        },
    ]

    entry_date = payload.entry_date or (period.pay_date or period.end_date)
    ref = f"PAYROLL-{period.period_key}-{str(run.id).replace('-', '')[:8]}"

    try:
        je = create_journal_entry(
            db,
            entry_date=entry_date,
            memo=payload.memo or f"Payroll run {run.run_no} for {period.period_key}",
            currency_code=payload.currency_code,
            reference_no=ref,
            source_module="payroll",
            source_id=str(run.id),
            lines=lines,
            created_by_user_id=None,
        )
        je = post_journal_entry(db, je.id, posted_by_user_id=None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GL post failed: {e}")

    run.status = "posted"
    run.posted_at = datetime.utcnow()
    run.reference_no = ref
    run.meta = dict(run.meta or {})
    try:
        run.meta["gl_journal_id"] = int(getattr(je, "id", None) or getattr(je, "entry_no", None))
    except Exception:
        pass
    db.commit()
    db.refresh(run)

    return {
        "already_posted": False,
        "run": _run_out(run),
        "journal_entry": _je_info(db, run.meta.get("gl_journal_id"), ref),
        "total_gross": str(total_gross),
    }

# ----------------------------- NEW: HTML payslip endpoint ----------------------------- #

def _fmt_money(x: Decimal | float | str) -> str:
    try:
        d = Decimal(str(x))
        return f"{d:,.2f}"
    except Exception:
        return str(x)

def _render_payslip_html(emp: Employee, period: PayrollPeriod, slip: Payslip) -> str:
    comps = (slip.snapshot_json or {}).get("components", [])
    gov = (slip.snapshot_json or {}).get("gov", {})
    rows = "".join(
        f"<tr><td>{c.get('code','')}</td><td style='text-align:right'>{_fmt_money(c.get('amount','0'))}</td></tr>"
        for c in comps
    )
    gov_rows = "".join(
        f"<tr><td>{k.upper()}</td><td style='text-align:right'>{_fmt_money(v)}</td></tr>"
        for k, v in gov.items()
    )
    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>Payslip {slip.reference_no or slip.id}</title>
<style>
  body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial; margin: 24px; }}
  .card {{ max-width: 720px; margin: 0 auto; border: 1px solid #ddd; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }}
  h1 {{ font-size: 20px; margin: 0 0 12px; }}
  h2 {{ font-size: 16px; margin: 16px 0 8px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  td, th {{ padding: 6px 4px; border-bottom: 1px solid #eee; }}
  .totals td {{ font-weight: 600; }}
  .muted {{ color: #666; font-size: 12px; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px 16px; margin-bottom: 12px; }}
</style>
</head>
<body>
<div class="card">
  <h1>Payslip</h1>
  <div class="grid">
    <div><strong>Employee:</strong> {emp.first_name} {emp.last_name} ({emp.code})</div>
    <div><strong>Period:</strong> {period.period_key}</div>
    <div><strong>Reference:</strong> {slip.reference_no or slip.id}</div>
    <div><strong>Generated:</strong> {slip.created_at.strftime("%Y-%m-%d %H:%M") if slip.created_at else ""}</div>
  </div>

  <h2>Earnings</h2>
  <table>{rows or "<tr><td colspan='2' class='muted'>No earnings</td></tr>"}</table>

  <h2>Deductions (Gov)</h2>
  <table>{gov_rows or "<tr><td colspan='2' class='muted'>None</td></tr>"}</table>

  <h2>Totals</h2>
  <table class="totals">
    <tr><td>Gross Pay</td><td style="text-align:right">{_fmt_money(slip.gross_pay)}</td></tr>
    <tr><td>Total Deductions</td><td style="text-align:right">{_fmt_money(slip.total_deductions)}</td></tr>
    <tr><td>Net Pay</td><td style="text-align:right">{_fmt_money(slip.net_pay)}</td></tr>
  </table>

  <p class="muted">Note: This is a stub layout. Government deductions will be computed in a later step.</p>
</div>
</body>
</html>
    """.strip()
    return html

@router.get("/payslips/{payslip_id}.html", response_class=HTMLResponse)
def api_get_payslip_html(payslip_id: UUID, db: Session = Depends(_get_db)):
    slip = db.get(Payslip, payslip_id)
    if not slip:
        raise HTTPException(status_code=404, detail="Payslip not found")
    emp = db.get(Employee, slip.employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee missing")
    run = db.get(PayrollRun, slip.run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run missing")
    period = db.get(PayrollPeriod, run.period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Period missing")
    return _render_payslip_html(emp, period, slip)
