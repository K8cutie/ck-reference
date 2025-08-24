# app/schemas/parishioners.py
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict


class ParishionerBase(BaseModel):
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    suffix: Optional[str] = None
    contact_number: Optional[str] = None

    # Pydantic v2: allows ORM objects to be returned directly
    model_config = ConfigDict(from_attributes=True)


class ParishionerCreate(ParishionerBase):
    # first_name and last_name remain required; others are optional
    pass


class ParishionerUpdate(BaseModel):
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    suffix: Optional[str] = None
    contact_number: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ParishionerRead(ParishionerBase):
    id: int


# Back-compat alias (if older code imports ParishionerOut)
ParishionerOut = ParishionerRead
