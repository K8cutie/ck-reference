# app/schemas/gl_accounting.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict, model_validator, computed_field


# ---------- Enums (align with DB ENUMs) ----------
class GLAccountType(str, Enum):
    asset = "asset"
    liability = "liability"
    equity = "equity"
    income = "income"
    expense = "expense"


class GLNormalSide(str, Enum):
    debit = "debit"
    credit = "credit"


# ---------- Accounts ----------
class GLAccountBase(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)
    type: GLAccountType
    normal_side: GLNormalSide
    is_cash: bool = False
    description: Optional[str] = None


class GLAccountCreate(GLAccountBase):
    pass


class GLAccountUpdate(BaseModel):
    code: Optional[str] = Field(default=None, max_length=32)
    name: Optional[str] = Field(default=None, max_length=255)
    type: Optional[GLAccountType] = None
    normal_side: Optional[GLNormalSide] = None
    is_cash: Optional[bool] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class GLAccountOut(GLAccountBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


# ---------- Journal (lines then header) ----------
class JournalLineIn(BaseModel):
    account_id: int
    description: Optional[str] = None
    # store as Decimal to match NUMERIC(14,2)
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    line_no: int = 1

    @model_validator(mode="after")
    def _one_side_only(self):
        d = self.debit or Decimal("0")
        c = self.credit or Decimal("0")
        # exactly one positive, the other zero
        if not (
            (d > 0 and c == 0) or
            (c > 0 and d == 0)
        ):
            raise ValueError("Each line must have either a positive debit or a positive credit, not both or neither.")
        return self


class JournalLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_id: int
    account_id: int
    description: Optional[str] = None
    debit: Decimal
    credit: Decimal
    line_no: int
    created_at: datetime
    updated_at: datetime


class JournalEntryBase(BaseModel):
    entry_date: date
    memo: Optional[str] = Field(default=None, max_length=512)
    currency_code: str = Field(default="PHP", min_length=3, max_length=3)
    reference_no: Optional[str] = Field(default=None, max_length=64)
    source_module: Optional[str] = Field(default=None, max_length=64)
    source_id: Optional[str] = Field(default=None, max_length=64)


class JournalEntryCreate(JournalEntryBase):
    lines: List[JournalLineIn]


class JournalEntryOut(JournalEntryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_no: int
    is_locked: bool
    posted_at: Optional[datetime] = None
    created_by_user_id: Optional[int] = None
    posted_by_user_id: Optional[int] = None
    locked_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    lines: List[JournalLineOut]

    @computed_field
    def total_debits(self) -> Decimal:  # type: ignore[override]
        return sum((l.debit or Decimal("0")) for l in self.lines)

    @computed_field
    def total_credits(self) -> Decimal:  # type: ignore[override]
        return sum((l.credit or Decimal("0")) for l in self.lines)

    @computed_field
    def is_balanced(self) -> bool:  # type: ignore[override]
        return (self.total_debits - self.total_credits).quantize(Decimal("0.01")) == Decimal("0.00")


# ---------- Audit ----------
class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    entity_id: Optional[str] = None
    action: str
    user_id: Optional[str] = None
    details: Optional[str] = None
    created_at: datetime
