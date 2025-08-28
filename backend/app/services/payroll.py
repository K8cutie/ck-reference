# backend/app/services/payroll.py
"""
Payroll service – minimal compute stub for MVP.

Scope (stub):
- create_employee, create_period, create_run helpers
- compute_run_basic(run_id): creates BASIC earning items and a payslip per active employee
  • Government deductions now wired via payroll_rates helpers (EE portions only for now)
  • BASIC amount heuristic:
      - monthly  -> monthly_rate (or 0)
      - daily    -> daily_rate * 26 (default working days)
      - hourly   -> hourly_rate * 8 * 26 (default hours/day * days)
- reference_no pattern for payslips (UNIQUE): PAY-{YYYYMM}-{empCode}-{run8}
- Idempotency: if a payslip already exists for (run_id, employee_id), skip
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models.payroll import (
    Employee,
    PayrollPeriod,
    PayrollRun,
    PayrollItem,
    Payslip,
)
from app.schemas.payroll import (
    EmployeeCreate,
    PayrollPeriodCreate,
    PayrollRunCreate,
)

# NEW: gov deductions loader (returns Decimal values; PhilHealth/Pag-IBIG have defaults)
from app.services.payroll_rates import compute_government_deductions as _gov_all


# ----------------------------- Decimal helpers ----------------------------- #

def D(val) -> Decimal:
    try:
        return val if isinstance(val, Decimal) else Decimal(str(val))
    except Exception:
        return Decimal("0")

def q2(val) -> Decimal:
    return D(val).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ----------------------------- Create helpers ----------------------------- #

def create_employee(db: Session, data: EmployeeCreate) -> Employee:
    emp = Employee(
        code=data.code,
        first_name=data.first_name,
        last_name=data.last_name,
        active=data.active,
        pay_type=data.pay_type,
        monthly_rate=data.monthly_rate,
        daily_rate=data.daily_rate,
        hourly_rate=data.hourly_rate,
        tax_status=data.tax_status,
        sss_no=data.sss_no,
        philhealth_no=data.philhealth_no,
        pagibig_no=data.pagibig_no,
        tin=data.tin,
        hire_date=data.hire_date,
        termination_date=data.termination_date,
        meta=dict(data.meta or {}),
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


def create_period(db: Session, data: PayrollPeriodCreate) -> PayrollPeriod:
    period = PayrollPeriod(
        period_key=data.period_key,
        start_date=data.start_date,
        end_date=data.end_date,
        pay_date=data.pay_date,
        status=data.status,
        meta=dict(data.meta or {}),
    )
    db.add(period)
    db.commit()
    db.refresh(period)
    return period


def create_run(db: Session, data: PayrollRunCreate) -> PayrollRun:
    run = PayrollRun(
        period_id=data.period_id,
        notes=data.notes,
        status="draft",
        meta={},
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


# ------------------------------- Compute stub ------------------------------ #

DEFAULT_WORKING_DAYS = Decimal("26")
DEFAULT_HOURS_PER_DAY = Decimal("8")


def _compute_basic_amount(emp: Employee) -> Decimal:
    """Compute a stub BASIC amount from employee rates."""
    if emp.pay_type == "monthly":
        return q2(emp.monthly_rate or 0)
    if emp.pay_type == "daily":
        return q2(D(emp.daily_rate or 0) * DEFAULT_WORKING_DAYS)
    if emp.pay_type == "hourly":
        return q2(D(emp.hourly_rate or 0) * DEFAULT_HOURS_PER_DAY * DEFAULT_WORKING_DAYS)
    return Decimal("0.00")


def compute_run_basic(db: Session, run_id: uuid.UUID) -> Dict[str, int]:
    """
    Minimal compute: for each ACTIVE employee, create
      - one PayrollItem(kind='earning', code='BASIC', amount=basic)
      - one Payslip with gov deductions (EE portions only for now)

    Idempotent for a given (run_id, employee_id): if a payslip already exists, skip.
    reference_no is UNIQUE across ALL runs: PAY-{YYYYMM}-{empCode}-{run8}
    """
    run = db.get(PayrollRun, run_id)
    if not run:
        raise ValueError(f"PayrollRun not found: {run_id}")

    period = db.get(PayrollPeriod, run.period_id)
    if not period:
        raise ValueError(f"PayrollPeriod not found for run {run_id}")

    # Gather active employees
    employees: list[Employee] = (
        db.query(Employee).filter(Employee.active.is_(True)).order_by(Employee.code).all()
    )

    # Idempotency: skip employees already computed for this run
    existing_emp_ids = {
        row.employee_id
        for row in db.query(Payslip.employee_id).filter(Payslip.run_id == run.id).all()
    }

    made_items = 0
    made_slips = 0

    yyyymm = period.start_date.strftime("%Y%m")
    run8 = str(run.id).replace("-", "")[:8]

    for emp in employees:
        if emp.id in existing_emp_ids:
            continue

        basic = _compute_basic_amount(emp)

        # --- Government deductions (EE portions only for now) ---
        gov = _gov_all(monthly_basic=basic, taxable_monthly=basic, status=(emp.tax_status or "S"))
        sss_ee        = q2(gov["sss"].get("ee", 0))
        philhealth_ee = q2(gov["philhealth"].get("ee", 0))
        pagibig_ee    = q2(gov["pagibig"].get("ee", 0))
        wht_tax       = q2(gov["withholding"].get("tax", 0))

        total_deductions = q2(sss_ee + philhealth_ee + pagibig_ee + wht_tax)
        net = q2(basic - total_deductions)

        # Create BASIC earning line
        item = PayrollItem(
            run_id=run.id,
            employee_id=emp.id,
            kind="earning",
            code="BASIC",
            quantity=Decimal("1"),
            rate=basic,
            amount=basic,
            taxable=True,
            meta={},
        )
        db.add(item)
        made_items += 1

        # UNIQUE per-run payslip reference (prevents collisions across runs in the same month)
        ref = f"PAY-{yyyymm}-{emp.code}-{run8}"

        slip = Payslip(
            run_id=run.id,
            employee_id=emp.id,
            gross_pay=basic,
            total_deductions=total_deductions,
            net_pay=net,
            snapshot_json={
                "components": [
                    {"kind": "earning", "code": "BASIC", "amount": str(basic)}
                ],
                "gov": {
                    "sss": str(sss_ee),
                    "philhealth": str(philhealth_ee),
                    "pagibig": str(pagibig_ee),
                    "withholding_tax": str(wht_tax),
                },
                "notes": "stub-compute-basic + gov (EE) wired; values depend on rate tables",
            },
            reference_no=ref,
            html=None,  # generated later
        )
        db.add(slip)
        made_slips += 1

    # mark run status if we created anything
    if made_items > 0 or made_slips > 0:
        run.status = "computed"

    db.commit()

    return {"items": made_items, "payslips": made_slips, "employees": len(employees)}
