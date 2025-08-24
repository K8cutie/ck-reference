# backend/app/models/expense.py
from __future__ import annotations

import enum
from sqlalchemy import (
    Column, Integer, Date, Numeric, String, Text, DateTime,
    ForeignKey, Enum as SAEnum, func
)
from app.db import Base  # ✅ fix: import Base from app.db


class ExpenseStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    expense_date = Column(Date, nullable=False, index=True)
    amount = Column(Numeric(14, 2), nullable=False)

    category_id = Column(
        Integer, ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True, index=True
    )

    vendor_name = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)

    # Use existing Postgres enum created by Alembic (create_type=False)
    status = Column(
        SAEnum(ExpenseStatus, name="expense_status", create_type=False),
        nullable=False, server_default="PENDING", index=True
    )
    due_date = Column(Date, nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)

    payment_method = Column(String(50), nullable=True)
    reference_no = Column(String(100), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
