from __future__ import annotations
from typing import List
from pydantic import BaseModel, Field

# ---------- detail models for each rite ----------

class BaptismDetails(BaseModel):
    mother: str
    father: str
    child_name: str
    god_parents: List[str] = Field(..., min_length=2, max_length=10)

class MarriageDetails(BaseModel):
    bride: str
    groom: str
    place_of_marriage: str
    witnesses: List[str]
