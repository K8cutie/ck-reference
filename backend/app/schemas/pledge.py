from __future__ import annotations
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, constr
from app.models.pledge import PledgeStatus as ModelPledgeStatus, PledgeFrequency as ModelPledgeFrequency
from app.models.transactions import PaymentMethod as ModelPaymentMethod

class PledgeBase(BaseModel):
    parishioner_id: int | None = None
    fund_id: int | None = None
    pledge_date: date
    amount_total: Decimal = Field(gt=0)
    frequency: ModelPledgeFrequency = ModelPledgeFrequency.one_time
    notes: str | None = None

class PledgeCreate(PledgeBase):
    status: ModelPledgeStatus = ModelPledgeStatus.ACTIVE

class PledgeUpdate(BaseModel):
    parishioner_id: int | None = None
    fund_id: int | None = None
    pledge_date: date | None = None
    amount_total: Decimal | None = None
    frequency: ModelPledgeFrequency | None = None
    status: ModelPledgeStatus | None = None
    notes: str | None = None

class PledgeOut(PledgeBase):
    id: int
    status: ModelPledgeStatus
    # computed fields
    paid_to_date: Decimal
    remaining: Decimal
    model_config = ConfigDict(from_attributes=True)

# Record a pledge payment -> creates an INCOME transaction tied to pledge_id
class PledgePaymentCreate(BaseModel):
    date: date
    amount: Decimal = Field(gt=0)
    account_id: int
    payment_method: ModelPaymentMethod | None = None
    reference_no: constr(strip_whitespace=True, max_length=100) | None = None
    description: constr(strip_whitespace=True, max_length=255) | None = "Pledge payment"
