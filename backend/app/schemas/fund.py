from __future__ import annotations
from pydantic import BaseModel, ConfigDict, constr

class FundBase(BaseModel):
    name: constr(strip_whitespace=True, min_length=1, max_length=100)
    code: constr(strip_whitespace=True, max_length=50) | None = None
    restricted: bool = False
    description: str | None = None

class FundCreate(FundBase):
    pass

class FundUpdate(BaseModel):
    name: constr(strip_whitespace=True, min_length=1, max_length=100) | None = None
    code: constr(strip_whitespace=True, max_length=50) | None = None
    restricted: bool | None = None
    description: str | None = None

class FundOut(FundBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
