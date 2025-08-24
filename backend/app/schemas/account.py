from __future__ import annotations
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, constr
from app.models.account import AccountType as ModelAccountType

class AccountBase(BaseModel):
    name: constr(strip_whitespace=True, min_length=1, max_length=100)
    type: ModelAccountType
    institution: str | None = None
    account_no: str | None = None
    currency: constr(min_length=3, max_length=3) = "PHP"
    opening_balance: Decimal = Field(default=Decimal("0"))

class AccountCreate(AccountBase):
    active: bool = True

class AccountUpdate(BaseModel):
    name: constr(strip_whitespace=True, min_length=1, max_length=100) | None = None
    type: ModelAccountType | None = None
    institution: str | None = None
    account_no: str | None = None
    currency: constr(min_length=3, max_length=3) | None = None
    opening_balance: Decimal | None = None
    active: bool | None = None

class AccountOut(AccountBase):
    id: int
    active: bool
    model_config = ConfigDict(from_attributes=True)
