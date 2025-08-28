# backend/app/api/payroll.py
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from fastapi.responses import HTMLResponse, StreamingResponse
import sqlalchemy as sa
import io, csv

try:
    from app.db.session import get_db as _get_db
except Exception:  # pragma: no cover
    from app.db import get_db as _get_db

from app.models.payroll import Employee, PayrollPeriod, PayrollRun, Payslip
from app.services.gl_accounting import create_journal_entry, post_journal_entry

# rates helpers (used for detailed GL posting & summaries)
from app.services.payroll_rates import (
    compute_sss, compute_philhealth, compute_pagibig, compute_withholding,
)

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

# ----------------------------- basic CRUD ----------------------------- #

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

# ----------------------------- simple post (kept) ----------------------------- #

class PostRunToGLIn(BaseModel):
    debit_account_id: int
    credit_account_id: int
    memo: Optional[str] = None
    currency_code: str = "PHP"
    entry_date: Optional[date] = None

@router.post("/runs/{run_id}/post")
def api_post_run_to_gl(run_id: UUID, payload: PostRunToGLIn = Body(...), db: Session = Depends(_get_db)):
    run = db.get(PayrollRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="PayrollRun not found")
    period = db.get(PayrollPeriod, run.period_id)
    if not period:
        raise HTTPException(status_code=400, detail="PayrollPeriod missing for run")
    slips: List[Payslip] = db.query(Payslip).filter(Payslip.run_id == run.id).all()
    if not slips:
        raise HTTPException(status_code=400, detail="No payslips to post for this run (compute first)")

    total_gross = sum(Decimal(s.gross_pay or 0) for s in slips)
    entry_date = payload.entry_date or (period.pay_date or period.end_date)
    ref = f"PAYROLL-{period.period_key}-{str(run.id).replace('-', '')[:8]}"

    lines = [
        {"account_id": int(payload.debit_account_id), "description": f"Payroll gross – {period.period_key}", "debit": float(total_gross), "credit": 0.0},
        {"account_id": int(payload.credit_account_id), "description": f"Payroll gross – {period.period_key}", "debit": 0.0, "credit": float(sum(Decimal(s.net_pay or 0) for s in slips))},
    ]

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
    run.status = "posted"; run.posted_at = datetime.utcnow(); run.reference_no = ref; run.meta = dict(run.meta or {}); db.commit(); db.refresh(run)
    return {"already_posted": False, "run": _run_out(run), "journal_entry": {"id": je.id, "reference_no": ref}, "total_gross": str(total_gross)}

# ----------------------------- detailed post (EE/ER split) ----------------------------- #

class PostRunDetailedIn(BaseModel):
    salary_expense_account_id: int = Field(..., description="Debit: Salaries & Wages expense")
    cash_account_id: int = Field(..., description="Credit: Cash/Bank (net pay)")
    liabilities: Dict[str, int] = Field(..., description="Payables account ids: keys = sss|philhealth|pagibig|withholding")
    er_expenses: Dict[str, int] = Field(..., description="Employer contribution expense accounts: keys = sss|philhealth|pagibig")
    memo: Optional[str] = None
    currency_code: str = "PHP"
    entry_date: Optional[date] = None

@router.post("/runs/{run_id}/post-detailed")
def api_post_run_detailed(run_id: UUID, payload: PostRunDetailedIn = Body(...), db: Session = Depends(_get_db)):
    run = db.get(PayrollRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="PayrollRun not found")
    period = db.get(PayrollPeriod, run.period_id)
    if not period:
        raise HTTPException(status_code=400, detail="PayrollPeriod missing for run")
    slips: List[Payslip] = db.query(Payslip).filter(Payslip.run_id == run.id).all()
    if not slips:
        raise HTTPException(status_code=400, detail="No payslips to post for this run (compute first)")

    total_gross = Decimal("0"); total_net = Decimal("0")
    ee_sss = Decimal("0"); ee_ph = Decimal("0"); ee_pag = Decimal("0"); ee_bir = Decimal("0")
    er_sss = Decimal("0"); er_ph = Decimal("0"); er_pag = Decimal("0")

    for s in slips:
        g = Decimal(s.gross_pay or 0)
        total_gross += g
        total_net += Decimal(s.net_pay or 0)
        gov = (s.snapshot_json or {}).get("gov", {})
        ee_sss += Decimal(str(gov.get("sss", "0")))
        ee_ph  += Decimal(str(gov.get("philhealth", "0")))
        ee_pag += Decimal(str(gov.get("pagibig", "0")))
        ee_bir += Decimal(str(gov.get("withholding_tax", "0")))
        er_sss += compute_sss(g)["er"]
        er_ph  += compute_philhealth(g)["er"]
        er_pag += compute_pagibig(g)["er"]

    entry_date = payload.entry_date or (period.pay_date or period.end_date)
    ref = f"PAYROLL-{period.period_key}-{str(run.id).replace('-', '')[:8]}"

    lines: List[Dict[str, Any]] = []
    lines.append({"account_id": int(payload.salary_expense_account_id), "description": f"Salaries & Wages – {period.period_key}", "debit": float(total_gross), "credit": 0.0})
    if er_sss > 0: lines.append({"account_id": int(payload.er_expenses["sss"]), "description": f"SSS Employer – {period.period_key}", "debit": float(er_sss), "credit": 0.0})
    if er_ph  > 0: lines.append({"account_id": int(payload.er_expenses["philhealth"]), "description": f"PhilHealth Employer – {period.period_key}", "debit": float(er_ph), "credit": 0.0})
    if er_pag > 0: lines.append({"account_id": int(payload.er_expenses["pagibig"]), "description": f"Pag-IBIG Employer – {period.period_key}", "debit": float(er_pag), "credit": 0.0})

    if ee_bir > 0: lines.append({"account_id": int(payload.liabilities["withholding"]), "description": f"BIR Withholding – {period.period_key}", "debit": 0.0, "credit": float(ee_bir)})
    if (ee_sss + er_sss) > 0: lines.append({"account_id": int(payload.liabilities["sss"]), "description": f"SSS Payable – {period.period_key}", "debit": 0.0, "credit": float(ee_sss + er_sss)})
    if (ee_ph + er_ph) > 0:   lines.append({"account_id": int(payload.liabilities["philhealth"]), "description": f"PhilHealth Payable – {period.period_key}", "debit": 0.0, "credit": float(ee_ph + er_ph)})
    if (ee_pag + er_pag) > 0: lines.append({"account_id": int(payload.liabilities["pagibig"]), "description": f"Pag-IBIG Payable – {period.period_key}", "debit": 0.0, "credit": float(ee_pag + er_pag)})

    lines.append({"account_id": int(payload.cash_account_id), "description": f"Net Payroll – {period.period_key}", "debit": 0.0, "credit": float(total_net)})

    je = create_journal_entry(
        db,
        entry_date=entry_date,
        memo=payload.memo or f"Payroll run {run.run_no} (detailed) for {period.period_key}",
        currency_code=payload.currency_code,
        reference_no=ref,
        source_module="payroll",
        source_id=str(run.id),
        lines=lines,
        created_by_user_id=None,
    )
    je = post_journal_entry(db, je.id, posted_by_user_id=None)

    run.status = "posted"; run.posted_at = datetime.utcnow(); run.reference_no = ref
    run.meta = dict(run.meta or {})
    run.meta.update({
        "gl_journal_id": int(getattr(je, "id", None) or getattr(je, "entry_no", None)),
        "totals": {
            "gross": str(total_gross), "net": str(total_net),
            "ee": {"sss": str(ee_sss), "philhealth": str(ee_ph), "pagibig": str(ee_pag), "bir": str(ee_bir)},
            "er": {"sss": str(er_sss), "philhealth": str(er_ph), "pagibig": str(er_pag)},
        }
    })
    db.commit(); db.refresh(run)

    return {
        "run": _run_out(run),
        "journal_entry": {"id": je.id, "reference_no": ref},
        "totals": run.meta["totals"],
    }

# ----------------------------- run summary ----------------------------- #

@router.get("/runs/{run_id}/summary")
def api_run_summary(run_id: UUID, db: Session = Depends(_get_db)):
    run = db.get(PayrollRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="PayrollRun not found")
    period = db.get(PayrollPeriod, run.period_id)
    if not period:
        raise HTTPException(status_code=400, detail="PayrollPeriod missing for run")

    slips: List[Payslip] = db.query(Payslip).filter(Payslip.run_id == run.id).all()
    if not slips:
        return {"run": _run_out(run), "totals": {"count": 0}}

    total_gross = Decimal("0"); total_net = Decimal("0")
    ee = {"sss": Decimal("0"), "philhealth": Decimal("0"), "pagibig": Decimal("0"), "bir": Decimal("0")}
    er = {"sss": Decimal("0"), "philhealth": Decimal("0"), "pagibig": Decimal("0")}
    for s in slips:
        g = Decimal(s.gross_pay or 0)
        total_gross += g
        total_net += Decimal(s.net_pay or 0)
        gov = (s.snapshot_json or {}).get("gov", {})
        ee["sss"]        += Decimal(str(gov.get("sss", "0")))
        ee["philhealth"] += Decimal(str(gov.get("philhealth", "0")))
        ee["pagibig"]    += Decimal(str(gov.get("pagibig", "0")))
        ee["bir"]        += Decimal(str(gov.get("withholding_tax", "0")))
        er["sss"]        += compute_sss(g)["er"]
        er["philhealth"] += compute_philhealth(g)["er"]
        er["pagibig"]    += compute_pagibig(g)["er"]

    def _fmt(d: Dict[str, Decimal]) -> Dict[str, str]:
        return {k: str(v.quantize(Decimal("0.01"))) for k, v in d.items()}

    summary = {
        "count": len(slips),
        "gross": str(total_gross.quantize(Decimal("0.01"))),
        "net": str(total_net.quantize(Decimal("0.01"))),
        "ee": _fmt(ee),
        "er": _fmt(er),
    }

    je_id = (run.meta or {}).get("gl_journal_id")
    if je_id:
        summary["journal_entry"] = {"id": je_id, "reference_no": run.reference_no}

    return {"run": _run_out(run), "totals": summary}

# ----------------------------- CSV export ----------------------------- #

@router.get("/runs/{run_id}/export.csv")
def api_export_run_csv(run_id: UUID, db: Session = Depends(_get_db)):
    run = db.get(PayrollRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="PayrollRun not found")

    slips: List[Payslip] = (
        db.query(Payslip)
        .filter(Payslip.run_id == run.id)
        .order_by(Payslip.created_at.asc())
        .all()
    )
    if not slips:
        # return empty CSV with header
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(["reference_no","employee_code","employee_name","gross","sss","philhealth","pagibig","withholding_tax","net"])
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                                 headers={"Content-Disposition": f'attachment; filename="payroll_run_{run_id}.csv"'})

    # build employee lookup
    emp_ids = [s.employee_id for s in slips]
    emps = db.query(Employee).filter(Employee.id.in_(emp_ids)).all()
    emap = {e.id: e for e in emps}

    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["reference_no","employee_code","employee_name","gross","sss","philhealth","pagibig","withholding_tax","net"])
    for s in slips:
        e = emap.get(s.employee_id)
        code = getattr(e, "code", "")
        name = (getattr(e, "first_name", "") or "") + " " + (getattr(e, "last_name", "") or "")
        gov = (s.snapshot_json or {}).get("gov", {})
        row = [
            s.reference_no or str(s.id),
            code,
            name.strip(),
            str(s.gross_pay or "0.00"),
            str(gov.get("sss","0.00")),
            str(gov.get("philhealth","0.00")),
            str(gov.get("pagibig","0.00")),
            str(gov.get("withholding_tax","0.00")),
            str(s.net_pay or "0.00"),
        ]
        w.writerow(row)

    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="payroll_run_{run_id}.csv"'})

# ----------------------------- Payslip HTML ----------------------------- #

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
  body {{ font-family: ui-sans-serif, system-ui; margin: 24px; }}
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

  <p class="muted">Note: ER contributions affect GL posting, not net pay. EE amounts above are deducted from net.</p>
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
