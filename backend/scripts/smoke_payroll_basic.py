# backend/scripts/smoke_payroll_basic.py
"""
Smoke test for Payroll compute stub.

What it does:
1) Creates a unique EMP (monthly) so repeats won't collide
2) Creates/uses a payroll period for the current month
3) Creates a payroll run
4) Calls compute_run_basic(run_id)
5) Prints a compact JSON summary

No government deductions yet (SSS/PhilHealth/Pag-IBIG/BIR).
"""

from __future__ import annotations

# --- PATH SHIM: ensure 'app' package is importable when running this script ---
import os, sys
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))          # .../backend/scripts
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))   # .../backend
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import json
import uuid
from datetime import date, timedelta, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import project services/models
from app.services.payroll import (
    create_employee,
    create_period,
    create_run,
    compute_run_basic,
)
from app.schemas.payroll import (
    EmployeeCreate,
    PayrollPeriodCreate,
    PayrollRunCreate,
)
from app.models.payroll import Employee, PayrollPeriod, PayrollRun, Payslip


def _month_bounds(d: date) -> tuple[date, date]:
    start = d.replace(day=1)
    next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    end = next_month - timedelta(days=1)
    return start, end


def _get_session():
    """
    Build a DB session from DATABASE_URL. We don't import the app's SessionLocal
    to keep this script stand-alone and robust.
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set. Activate venv and ensure env is loaded.")
    eng = create_engine(db_url, pool_pre_ping=True)
    return sessionmaker(bind=eng, autoflush=False, autocommit=False)()


def main():
    today = date.today()
    start, end = _month_bounds(today)
    period_key = f"{today:%Y-%m}"  # keep canonical shape

    # Unique emp code every run to avoid payslip reference collision
    emp_code = f"SMK{datetime.now():%H%M%S}"

    db = _get_session()

    # 1) Employee (monthly, 20,000 for the stub)
    emp_in = EmployeeCreate(
        code=emp_code,
        first_name="Smoke",
        last_name="Tester",
        active=True,
        pay_type="monthly",
        monthly_rate=Decimal("20000.00"),
        daily_rate=None,
        hourly_rate=None,
        tax_status=None,
        sss_no=None,
        philhealth_no=None,
        pagibig_no=None,
        tin=None,
        hire_date=start,
        termination_date=None,
        meta={"source": "smoke"},
    )
    emp = create_employee(db, emp_in)

    # 2) Period (get or create)
    period = db.query(PayrollPeriod).filter(PayrollPeriod.period_key == period_key).first()
    if not period:
        period_in = PayrollPeriodCreate(
            period_key=period_key,
            start_date=start,
            end_date=end,
            pay_date=end,
            status="draft",
            meta={"source": "smoke"},
        )
        period = create_period(db, period_in)

    # 3) Run (always create a fresh run for this smoke)
    run = create_run(db, PayrollRunCreate(period_id=period.id, notes="smoke run"))

    # 4) Compute
    res = compute_run_basic(db, run.id)

    # 5) Grab the generated payslip for our new employee
    slip = (
        db.query(Payslip)
        .filter(Payslip.run_id == run.id, Payslip.employee_id == emp.id)
        .order_by(Payslip.created_at.desc())
        .first()
    )

    out = {
        "employee": {"id": str(emp.id), "code": emp.code},
        "period": {"id": str(period.id), "period_key": period.period_key},
        "run": {"id": str(run.id), "status": run.status},
        "compute": res,
        "payslip": {
            "id": str(slip.id) if slip else None,
            "reference_no": getattr(slip, "reference_no", None),
            "gross_pay": str(getattr(slip, "gross_pay", "")),
            "net_pay": str(getattr(slip, "net_pay", "")),
        },
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
