# backend/app/schemas/payroll.py
"""
Pydantic schemas for ClearKeep Payroll.

Covers:
- Employees
- Payroll Periods
- Payroll Runs
- Payroll Items (earnings/deductions/etc.)
- Payslips (read-only)
- Payroll Configs

Notes:
- Keep string enums aligned with DB enum values created in migration a7a3d2b18c01.
- Monetary values use Decimal to avoid float rounding.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ------------------------- Enum Literals (string) ------------------------- #
PayType = Literal["monthly", "daily", "hourly"]

PeriodStatus = Literal["draft", "open", "closed"]

RunStatus = Literal["draft", "computed", "posted"]

ItemKind = Literal["earning", "deduction", "tax", "employer_contrib"]


# ------------------------------- Employees -------------------------------- #
class EmployeeBase(BaseModel):
    code: str = Field(..., max_length=32)
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)

    active: bool = True
    pay_type: PayType

    monthly_rate: Optional[Decimal] = Field(None, description="Monthly basic rate (if pay_type=monthly)")
    daily_rate: Optional[Decimal] = Field(None, description="Daily basic rate (if pay_type=daily)")
    hourly_rate: Optional[Decimal] = Field(None, description="Hourly basic rate (if pay_type=hourly)")

    tax_status: Optional[str] = Field(None, max_length=20)
    sss_no: Optional[str] = Field(None, max_length=20)
    philhealth_no: Optional[str] = Field(None, max_length=20)
    pagibig_no: Optional[str] = Field(None, max_length=20)
    tin: Optional[str] = Field(None, max_length=20)

    hire_date: Optional[date] = None
    termination_date: Optional[date] = None

    meta: Dict[str, Any] = Field(default_factory=dict)


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    # All optional for PATCH-style updates
    code: Optional[str] = Field(None, max_length=32)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)

    active: Optional[bool] = None
    pay_type: Optional[PayType] = None

    monthly_rate: Optional[Decimal] = None
    daily_rate: Optional[Decimal] = None
    hourly_rate: Optional[Decimal] = None

    tax_status: Optional[str] = Field(None, max_length=20)
    sss_no: Optional[str] = Field(None, max_length=20)
    philhealth_no: Optional[str] = Field(None, max_length=20)
    pagibig_no: Optional[str] = Field(None, max_length=20)
    tin: Optional[str] = Field(None, max_length=20)

    hire_date: Optional[date] = None
    termination_date: Optional[date] = None

    meta: Optional[Dict[str, Any]] = None


class EmployeeOut(EmployeeBase):
    id: UUID
    created_at: datetime


# ---------------------------- Payroll Periods ----------------------------- #
class PayrollPeriodBase(BaseModel):
    period_key: str = Field(..., max_length=32, description="e.g., 2025-08 or 2025-08-15/30 for semi-monthly later")
    start_date: date
    end_date: date
    pay_date: date
    status: PeriodStatus = "draft"
    meta: Dict[str, Any] = Field(default_factory=dict)


class PayrollPeriodCreate(PayrollPeriodBase):
    pass


class PayrollPeriodOut(PayrollPeriodBase):
    id: UUID


# ------------------------------ Payroll Runs ------------------------------ #
class PayrollRunBase(BaseModel):
    period_id: UUID
    run_no: int = 1
    status: RunStatus = "draft"
    posted_at: Optional[datetime] = None
    reference_no: Optional[str] = Field(None, max_length=64)
    notes: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class PayrollRunCreate(BaseModel):
    period_id: UUID
    notes: Optional[str] = None


class PayrollRunOut(PayrollRunBase):
    id: UUID


# ------------------------------ Payroll Items ----------------------------- #
class PayrollItemBase(BaseModel):
    run_id: UUID
    employee_id: UUID
    kind: ItemKind
    code: str = Field(..., max_length=30)
    quantity: Decimal = Field(default=Decimal("0"))
    rate: Decimal = Field(default=Decimal("0"))
    amount: Decimal = Field(default=Decimal("0"))
    taxable: bool = True
    gl_account_id: Optional[UUID] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class PayrollItemCreate(PayrollItemBase):
    pass


class PayrollItemOut(PayrollItemBase):
    id: UUID


# -------------------------------- Payslips -------------------------------- #
class PayslipOut(BaseModel):
    id: UUID
    run_id: UUID
    employee_id: UUID

    gross_pay: Decimal
    total_deductions: Decimal
    net_pay: Decimal

    snapshot_json: Dict[str, Any]
    reference_no: Optional[str] = None
    html: Optional[str] = None
    created_at: datetime


# ---------------------------- Payroll Configs ----------------------------- #
class PayrollConfigBase(BaseModel):
    key: str = Field(..., max_length=64)
    value_json: Dict[str, Any] = Field(default_factory=dict)
    effective_from: date


class PayrollConfigCreate(PayrollConfigBase):
    pass


class PayrollConfigOut(PayrollConfigBase):
    id: UUID
