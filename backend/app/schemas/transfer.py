from __future__ import annotations
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, constr

class TransferCreate(BaseModel):
    date: date
    amount: Decimal = Field(gt=0)
    from_account_id: int
    to_account_id: int
    fund_id: int | None = None
    description: constr(strip_whitespace=True, max_length=255) | None = None
    transfer_ref: constr(strip_whitespace=True, max_length=100) | None = None
    batch_id: constr(strip_whitespace=True, max_length=100) | None = None
    # Optional separate refs if you want to track bank slips, etc.
    reference_no_from: constr(strip_whitespace=True, max_length=100) | None = None
    reference_no_to: constr(strip_whitespace=True, max_length=100) | None = None

class TransferOut(BaseModel):
    transfer_ref: str
    date: date
    amount: Decimal
    description: str | None
    fund_id: int | None
    from_account_id: int | None
    to_account_id: int | None
    expense_tx_id: int | None
    income_tx_id: int | None
    batch_id: str | None

    model_config = ConfigDict(from_attributes=True)

class VoidTransfer(BaseModel):
    reason: constr(strip_whitespace=True, max_length=255) | None = None
