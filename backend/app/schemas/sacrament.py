# app/schemas/sacrament.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, List, Optional, Dict, Any, Union

from pydantic import BaseModel, Field, ConfigDict


# ─────────────────────────────────────────────────────────────────────────────
# Detail models (per-type) – used for CREATE validation
# ─────────────────────────────────────────────────────────────────────────────

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


class ConfirmationDetails(BaseModel):
    confirmand: str
    sponsor_names: List[str]
    preparation_class_batch: Optional[str] = None


class FirstCommunionDetails(BaseModel):
    communicant: str
    preparation_class_batch: Optional[str] = None


class AnointingDetails(BaseModel):
    recipient: str
    location_administered: str
    is_last_rites: bool = Field(
        False, description="True if administered as Viaticum / Last Rites"
    )


class FuneralDetails(BaseModel):
    deceased: str
    date_of_death: date
    burial_site: str


# ─────────────────────────────────────────────────────────────────────────────
# Base fields shared by every sacrament
# ─────────────────────────────────────────────────────────────────────────────

class _SacBase(BaseModel):
    parishioner_id: int
    date: date
    fee: Optional[Decimal] = None
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ─────────────────────────────────────────────────────────────────────────────
# Create-payload classes for each subtype (discriminated union)
# ─────────────────────────────────────────────────────────────────────────────

class BaptismCreate(_SacBase):
    sacrament_type: Literal["baptism"]
    details: BaptismDetails


class MarriageCreate(_SacBase):
    sacrament_type: Literal["marriage"]
    details: MarriageDetails


class ConfirmationCreate(_SacBase):
    sacrament_type: Literal["confirmation"]
    details: ConfirmationDetails


class FirstCommunionCreate(_SacBase):
    sacrament_type: Literal["first_communion"]
    details: FirstCommunionDetails


class AnointingCreate(_SacBase):
    sacrament_type: Literal["anointing"]
    details: AnointingDetails


class FuneralCreate(_SacBase):
    sacrament_type: Literal["funeral"]
    details: FuneralDetails


SacramentCreate = Annotated[
    Union[
        BaptismCreate,
        MarriageCreate,
        ConfirmationCreate,
        FirstCommunionCreate,
        AnointingCreate,
        FuneralCreate,
    ],
    Field(discriminator="sacrament_type"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Read model (returned by API)
# ─────────────────────────────────────────────────────────────────────────────

class SacramentRead(_SacBase):
    id: int
    sacrament_type: str
    details: Dict[str, Any]  # return raw JSON to client


# ─────────────────────────────────────────────────────────────────────────────
# Update model (PATCH) – flexible, includes sacrament_type + details
# ─────────────────────────────────────────────────────────────────────────────

class SacramentUpdate(BaseModel):
    parishioner_id: Optional[int] = None
    date: Optional[date] = None
    fee: Optional[Decimal] = None
    notes: Optional[str] = None

    # Allow changing type on PATCH; service will alias-map (e.g., "funeral" -> DEATH)
    sacrament_type: Optional[
        Literal[
            "baptism",
            "marriage",
            "confirmation",
            "first_communion",
            "anointing",
            "funeral",
        ]
    ] = None

    # For PATCH, keep this loose so partial updates are easy
    details: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)
