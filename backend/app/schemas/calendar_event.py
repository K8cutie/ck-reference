from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


# ---------- Core DTOs ----------

class CalendarEventBase(BaseModel):
    title: str = Field(..., max_length=200)
    description: Optional[str] = None
    location: Optional[str] = Field(None, max_length=200)

    start_at: datetime
    end_at: datetime
    all_day: bool = False
    timezone: str = Field(default="Asia/Manila", max_length=64)

    # iCalendar RRULE string, e.g., "FREQ=WEEKLY;BYDAY=MO,WE,FR"
    rrule: Optional[str] = None

    # Exception dates for recurrence (each must be tz-aware)
    exdates: List[datetime] = Field(default_factory=list)

    # Soft toggle (not deletion)
    is_active: bool = True

    # Pydantic v2 ORM mode
    model_config = ConfigDict(from_attributes=True)

    @field_validator("start_at", "end_at")
    @classmethod
    def _require_tzaware(cls, v: datetime) -> datetime:
        """Ensure datetimes are timezone-aware (include an offset)."""
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError(
                "Datetime must include a timezone offset (e.g., '2025-08-09T09:00:00+08:00')."
            )
        return v

    @field_validator("exdates")
    @classmethod
    def _exdates_tzaware(cls, v: List[datetime]) -> List[datetime]:
        for dt in v:
            if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
                raise ValueError("All exdates must be timezone-aware.")
        return v

    @model_validator(mode="after")
    def _end_after_start(self) -> "CalendarEventBase":
        if self.end_at < self.start_at:
            raise ValueError("end_at must be greater than or equal to start_at.")
        return self


class CalendarEventCreate(CalendarEventBase):
    """Payload for creating a (single or recurring) event."""
    # Inherit all fields; server will set id/created_at/updated_at.


class CalendarEventUpdate(BaseModel):
    """Patch-style update; all fields optional."""
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    location: Optional[str] = Field(None, max_length=200)

    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    all_day: Optional[bool] = None
    timezone: Optional[str] = Field(None, max_length=64)

    rrule: Optional[str] = None
    exdates: Optional[List[datetime]] = None

    is_active: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("start_at", "end_at")
    @classmethod
    def _require_tzaware_if_present(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return v
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError(
                "Datetime must include a timezone offset (e.g., '2025-08-09T09:00:00+08:00')."
            )
        return v

    @field_validator("exdates")
    @classmethod
    def _exdates_tzaware_if_present(cls, v: Optional[List[datetime]]) -> Optional[List[datetime]]:
        if v is None:
            return v
        for dt in v:
            if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
                raise ValueError("All exdates must be timezone-aware.")
        return v

    @model_validator(mode="after")
    def _end_after_start_if_both(self) -> "CalendarEventUpdate":
        if self.start_at is not None and self.end_at is not None:
            if self.end_at < self.start_at:
                raise ValueError("end_at must be greater than or equal to start_at.")
        return self


class CalendarEventRead(CalendarEventBase):
    """What the API returns for an event."""
    id: uuid.UUID

    # Expose linking fields so the UI can match SAC-{id}
    origin: Optional[str] = None
    external_ref: Optional[str] = None
    meta: dict = Field(default_factory=dict)

    created_at: datetime
    updated_at: datetime


# ---------- Recurrence Expansion DTO ----------

class CalendarOccurrenceRead(BaseModel):
    """Flattened instance produced by expanding a recurring event."""
    event_id: uuid.UUID
    title: str
    start_at: datetime
    end_at: datetime
    all_day: bool
    location: Optional[str] = None
    is_recurring: bool = False

    model_config = ConfigDict(from_attributes=True)
