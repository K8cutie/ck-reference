from __future__ import annotations
import uuid
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class SigmaLogBase(BaseModel):
    process: str
    ctq: Optional[str] = None
    period_start: datetime
    period_end: datetime
    units: int = Field(gt=0)
    opportunities_per_unit: int = Field(gt=0)
    defects: int = Field(ge=0)
    notes: Optional[str] = None

class SigmaLogCreate(SigmaLogBase):
    pass

class SigmaLogRead(SigmaLogBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class SigmaSummaryRead(BaseModel):
    process: str
    from_at: datetime
    to_at: datetime
    units: int
    opportunities: int
    defects: int
    dpu: float
    dpmo: float
    fpy: float         # first pass yield (≈ e^-DPU)
    sigma_short: float # Z(short-term)
    sigma_long: float  # Z + 1.5

class ControlPoint(BaseModel):
    date: datetime            # start-of-day bucket (in tz)
    opportunities: int
    defects: int
    p_hat: float              # defects / opps that day
    ucl: float
    lcl: float

class ControlChartRead(BaseModel):
    process: str
    p_bar: float
    points: List[ControlPoint]
