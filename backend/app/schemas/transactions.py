# app/schemas/transactions.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_serializer


class TransactionType(str, Enum):
    income = "income"
    expense = "expense"


class PaymentMethod(str, Enum):
    cash = "cash"
    gcash = "gcash"
    bank_transfer = "bank_transfer"
    check = "check"
    other = "other"


class TransactionBase(BaseModel):
    date: date
    description: str
    amount: Decimal | float
    type: TransactionType
    category_id: Optional[int] = None
    parishioner_id: Optional[int] = None
    payment_method: PaymentMethod = PaymentMethod.cash
    reference_no: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TransactionCreate(TransactionBase):
    # keep strict defaults on create
    pass


class TransactionUpdate(BaseModel):
    date: Optional[date] = None
    description: Optional[str] = None
    amount: Optional[Decimal | float] = None
    type: Optional[TransactionType] = None
    category_id: Optional[int] = None
    parishioner_id: Optional[int] = None
    payment_method: Optional[PaymentMethod] = None
    reference_no: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TransactionRead(TransactionBase):
    id: int
    # allow legacy NULLs on reads
    payment_method: Optional[PaymentMethod] = PaymentMethod.cash

    # ensure JSON returns a number, not a string
    @field_serializer("amount")
    def _serialize_amount(self, v: Decimal | float):
        return float(v) if v is not None else v


# Back-compat for older imports
TransactionOut = TransactionRead
