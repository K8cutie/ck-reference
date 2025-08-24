from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

# ✅ Your project exposes Base in app/db.py
from app.db import Base


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default="Asia/Manila")

    # iCalendar RRULE string (e.g., "FREQ=WEEKLY;BYDAY=MO,WE,FR")
    rrule: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)

    # Exception dates (skip these specific occurrences)
    # Server default is set by the migration; no need to define here.
    exdates: Mapped[List[datetime]] = mapped_column(
        postgresql.ARRAY(DateTime(timezone=True)),
        nullable=False,
    )

    # 🔗 Linking to other modules (added)
    origin: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    external_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    meta: Mapped[dict] = mapped_column(postgresql.JSONB, nullable=False, default=dict)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<CalendarEvent id={self.id} title={self.title!r} start={self.start_at} end={self.end_at}>"
