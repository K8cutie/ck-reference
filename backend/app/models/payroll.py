# backend/app/models/payroll.py
"""
Payroll ORM models for ClearKeep.

Tables:
- employees
- payroll_periods
- payroll_runs
- payroll_items
- payslips
- payroll_configs
- employee_comp_history   <-- NEW (tracks promotions / salary changes)
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

# ✅ Project pattern: Base comes from app.db (see calendar_event.py)
from app.db import Base


# ---------- Enums (bind to existing DB enum types; do NOT create new ones) ----------
EmployeePayType = postgresql.ENUM(
    "monthly", "daily", "hourly", name="employee_pay_type", create_type=False
)
PayrollPeriodStatus = postgresql.ENUM(
    "draft", "open", "closed", name="payroll_period_status", create_type=False
)
PayrollRunStatus = postgresql.ENUM(
    "draft", "computed", "posted", name="payroll_run_status", create_type=False
)
PayrollItemKind = postgresql.ENUM(
    "earning", "deduction", "tax", "employer_contrib", name="payroll_item_kind", create_type=False
)


# --------------------------------- MODELS --------------------------------- #

class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Contact & address
    contact_no: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    address_line1: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    barangay: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    province: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Employment status
    hire_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    termination_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    # Pay & rates
    pay_type: Mapped[str] = mapped_column(EmployeePayType, nullable=False)
    monthly_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    daily_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    hourly_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)

    # Gov/tax
    tax_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    sss_no: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    philhealth_no: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    pagibig_no: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    tin: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Emergency & notes
    emergency_contact_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    emergency_contact_no: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)

    # Misc
    meta: Mapped[dict] = mapped_column(postgresql.JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    items: Mapped[list["PayrollItem"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan"
    )
    payslips: Mapped[list["Payslip"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan"
    )
    comp_history: Mapped[list["EmployeeCompHistory"]] = relationship(   # NEW
        back_populates="employee", cascade="all, delete-orphan", order_by="desc(EmployeeCompHistory.effective_date)"
    )

    def __repr__(self) -> str:
        return f"<Employee {self.code} {self.last_name}>"


class EmployeeCompHistory(Base):
    """
    Tracks changes in compensation (promotions, rate adjustments) for an employee.
    Mirrors columns in the migration 4c95c4046b3e.
    """
    __tablename__ = "employee_comp_history"

    id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )

    effective_date: Mapped[date] = mapped_column(Date(), nullable=False)
    change_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # e.g., promotion, adjustment
    reason: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)

    # Old/New pay types & rates
    old_pay_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    new_pay_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    old_monthly_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    new_monthly_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    old_daily_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    new_daily_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    old_hourly_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    new_hourly_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationship
    employee: Mapped["Employee"] = relationship(back_populates="comp_history")

    def __repr__(self) -> str:
        return f"<EmployeeCompHistory emp={self.employee_id} eff={self.effective_date}>"


class PayrollPeriod(Base):
    __tablename__ = "payroll_periods"

    id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    period_key: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)

    start_date: Mapped[date] = mapped_column(Date(), nullable=False)
    end_date: Mapped[date] = mapped_column(Date(), nullable=False)
    pay_date: Mapped[date] = mapped_column(Date(), nullable=False)
    status: Mapped[str] = mapped_column(PayrollPeriodStatus, nullable=False, server_default="draft")
    meta: Mapped[dict] = mapped_column(postgresql.JSONB, nullable=False, default=dict)

    runs: Mapped[list["PayrollRun"]] = relationship(
        back_populates="period", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PayrollPeriod {self.period_key} {self.start_date}..{self.end_date}>"


class PayrollRun(Base):
    __tablename__ = "payroll_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    period_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True), ForeignKey("payroll_periods.id", ondelete="RESTRICT"), nullable=False
    )

    run_no: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    status: Mapped[str] = mapped_column(PayrollRunStatus, nullable=False, server_default="draft")
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reference_no: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    meta: Mapped[dict] = mapped_column(postgresql.JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    period: Mapped["PayrollPeriod"] = relationship(back_populates="runs")
    items: Mapped[list["PayrollItem"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    payslips: Mapped[list["Payslip"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PayrollRun {self.reference_no or self.run_no} status={self.status}>"


class PayrollItem(Base):
    __tablename__ = "payroll_items"

    id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True), ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False
    )

    kind: Mapped[str] = mapped_column(PayrollItemKind, nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
    rate: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    taxable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    gl_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        postgresql.UUID(as_uuid=True), nullable=True
    )
    meta: Mapped[dict] = mapped_column(postgresql.JSONB, nullable=False, default=dict)

    run: Mapped["PayrollRun"] = relationship(back_populates="items")
    employee: Mapped["Employee"] = relationship(back_populates="items")

    def __repr__(self) -> str:
        return f"<PayrollItem {self.code} {self.amount}>"


class Payslip(Base):
    __tablename__ = "payslips"

    id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True), ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False
    )

    gross_pay: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    total_deductions: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    net_pay: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")

    snapshot_json: Mapped[dict] = mapped_column(postgresql.JSONB, nullable=False, default=dict)
    reference_no: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)
    html: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    run: Mapped["PayrollRun"] = relationship(back_populates="payslips")
    employee: Mapped["Employee"] = relationship(back_populates="payslips")

    def __repr__(self) -> str:
        return f"<Payslip {self.reference_no or self.id} {self.net_pay}>"


class PayrollConfig(Base):
    __tablename__ = "payroll_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    value_json: Mapped[dict] = mapped_column(postgresql.JSONB, nullable=False, default=dict)
    effective_from: Mapped[date] = mapped_column(Date(), nullable=False)

    def __repr__(self) -> str:
        return f"<PayrollConfig {self.key} @ {self.effective_from}>"
