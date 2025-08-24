from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, condecimal


class ExpenseStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"


# Decimal type aligned with DB (NUMERIC(14,2))
Amount = condecimal(max_digits=14, decimal_places=2, gt=0)


class ExpenseBase(BaseModel):
    expense_date: date
    amount: Amount
    category_id: Optional[int] = Field(default=None)
    vendor_name: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    status: ExpenseStatus = ExpenseStatus.PENDING
    due_date: Optional[date] = None
    paid_at: Optional[datetime] = None
    payment_method: Optional[str] = Field(default=None, max_length=50)
    reference_no: Optional[str] = Field(default=None, max_length=100)


class ExpenseCreate(ExpenseBase):
    """Payload for creating an expense."""
    pass


class ExpenseUpdate(BaseModel):
    """Partial update; send only fields to change."""
    expense_date: Optional[date] = None
    amount: Optional[Amount] = None
    category_id: Optional[int] = None
    vendor_name: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    status: Optional[ExpenseStatus] = None
    due_date: Optional[date] = None
    paid_at: Optional[datetime] = None
    payment_method: Optional[str] = Field(default=None, max_length=50)
    reference_no: Optional[str] = Field(default=None, max_length=100)


class ExpenseOut(ExpenseBase):
    """Response model."""
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
