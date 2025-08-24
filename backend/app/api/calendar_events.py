from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone, date as _date
from typing import List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, File, status
from pydantic import BaseModel, field_validator
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.calendar_event import CalendarEvent
from app.schemas.calendar_event import (
    CalendarEventCreate,
    CalendarEventUpdate,
    CalendarEventRead,
    CalendarOccurrenceRead,
)
from dateutil.rrule import rrulestr

router = APIRouter(prefix="/calendar", tags=["calendar"])


# --------------------------- Helpers ---------------------------

def _utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc)


def _overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start <= b_end and a_end >= b_start


def _sanitize_ics_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return (
        text.replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _format_ics_dt(dt: datetime) -> str:
    return _utc(dt).strftime("%Y%m%dT%H%M%SZ")


def _default_range(now: Optional[datetime] = None) -> tuple[datetime, datetime]:
    base = now or datetime.now(timezone.utc)
    return base, base + timedelta(days=30)


def _event_tz(base_tz: Optional[str], fallback_dt: datetime) -> timezone:
    """Return a tzinfo for the event with Windows-safe fallbacks."""
    if base_tz:
        try:
            return ZoneInfo(base_tz)
        except (ZoneInfoNotFoundError, Exception):
            if base_tz in {
                "Asia/Manila", "Asia/Singapore", "Asia/Shanghai",
                "Asia/Hong_Kong", "Asia/Brunei", "Etc/GMT-8"
            }:
                return timezone(timedelta(hours=8))
    return fallback_dt.tzinfo or timezone.utc


def _expand_event(
    event: CalendarEvent,
    range_start: datetime,
    range_end: datetime,
) -> List[CalendarOccurrenceRead]:
    occurrences: List[CalendarOccurrenceRead] = []

    # Non-recurring
    if not event.rrule:
        if _overlaps(event.start_at, event.end_at, range_start, range_end):
            occurrences.append(
                CalendarOccurrenceRead(
                    event_id=event.id,
                    title=event.title,
                    start_at=event.start_at,
                    end_at=event.end_at,
                    all_day=event.all_day,
                    location=event.location,
                    is_recurring=False,
                )
            )
        return occurrences

    # Recurring
    duration = event.end_at - event.start_at
    rule = rrulestr(event.rrule, dtstart=event.start_at, forceset=False)
    instances: List[datetime] = rule.between(range_start, range_end, inc=True)

    ex_utc_seconds = {
        int(_utc(x).replace(microsecond=0).timestamp())
        for x in (event.exdates or [])
    }

    for inst_start in instances:
        if inst_start.tzinfo is None or inst_start.tzinfo.utcoffset(inst_start) is None:
            inst_start = inst_start.replace(tzinfo=event.start_at.tzinfo)

        inst_end = inst_start + duration

        if int(_utc(inst_start).replace(microsecond=0).timestamp()) in ex_utc_seconds:
            continue

        if _overlaps(inst_start, inst_end, range_start, range_end):
            occurrences.append(
                CalendarOccurrenceRead(
                    event_id=event.id,
                    title=event.title,
                    start_at=inst_start,
                    end_at=inst_end,
                    all_day=event.all_day,
                    location=event.location,
                    is_recurring=True,
                )
            )
    return occurrences


def _rrule_dict_to_text(rr: dict) -> Optional[str]:
    if not rr:
        return None
    parts = []
    for k, v in rr.items():
        key = str(k).upper()
        vals = v if isinstance(v, list) else [v]
        vals = [str(x).upper() for x in vals]
        parts.append(f"{key}={','.join(vals)}")
    return ";".join(parts)


def _tzname_from_tzinfo(tz) -> Optional[str]:
    # Try ZoneInfo.key or pytz-style .zone; fallback to common offsets
    name = getattr(tz, "key", None) or getattr(tz, "zone", None)
    if name:
        return name
    try:
        off = tz.utcoffset(datetime.now(timezone.utc))
    except Exception:
        return None
    if off is None:
        return None
    hours = int(off.total_seconds() // 3600)
    if hours == 8:
        return "Asia/Manila"
    if hours == 0:
        return "UTC"
    sign = "-" if hours > 0 else "+"
    return f"Etc/GMT{sign}{abs(hours)}"


# --------------------------- Exceptions Schemas ---------------------------

class _InstanceRef(BaseModel):
    instance_start_at: datetime

    @field_validator("instance_start_at")
    @classmethod
    def _tzaware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("instance_start_at must be timezone-aware")
        return v


class _InstanceEdit(_InstanceRef):
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    start_at: Optional[datetime] = None  # override start (tz-aware)
    end_at: Optional[datetime] = None    # override end (tz-aware)
    all_day: Optional[bool] = None
    timezone: Optional[str] = None

    @field_validator("start_at", "end_at")
    @classmethod
    def _opt_tzaware(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is not None and (v.tzinfo is None or v.tzinfo.utcoffset(v) is None):
            raise ValueError("start_at/end_at must be timezone-aware")
        return v


# --------------------------- CRUD ---------------------------

@router.post("/events", response_model=CalendarEventRead, status_code=status.HTTP_201_CREATED)
def create_event(payload: CalendarEventCreate, db: Session = Depends(get_db)) -> CalendarEventRead:
    evt = CalendarEvent(
        title=payload.title,
        description=payload.description,
        location=payload.location,
        start_at=payload.start_at,
        end_at=payload.end_at,
        all_day=payload.all_day,
        timezone=payload.timezone,
        rrule=payload.rrule,
        exdates=payload.exdates or [],
        is_active=payload.is_active,
    )
    db.add(evt)
    db.commit()
    db.refresh(evt)
    return evt


@router.get("/events/{event_id}", response_model=CalendarEventRead)
def get_event(event_id: uuid.UUID, db: Session = Depends(get_db)) -> CalendarEventRead:
    evt = db.get(CalendarEvent, event_id)
    if not evt or not evt.is_active:
        raise HTTPException(status_code=404, detail="Event not found")
    return evt


@router.put("/events/{event_id}", response_model=CalendarEventRead)
def update_event(event_id: uuid.UUID, payload: CalendarEventUpdate, db: Session = Depends(get_db)) -> CalendarEventRead:
    evt: Optional[CalendarEvent] = db.get(CalendarEvent, event_id)
    if not evt or not evt.is_active:
        raise HTTPException(status_code=404, detail="Event not found")

    for field in (
        "title", "description", "location", "start_at", "end_at",
        "all_day", "timezone", "rrule", "is_active"
    ):
        val = getattr(payload, field)
        if val is not None:
            setattr(evt, field, val)

    if payload.exdates is not None:
        evt.exdates = payload.exdates

    if evt.end_at < evt.start_at:
        raise HTTPException(status_code=400, detail="end_at must be >= start_at")

    db.add(evt)
    db.commit()
    db.refresh(evt)
    return evt


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    evt: Optional[CalendarEvent] = db.get(CalendarEvent, event_id)
    if not evt or not evt.is_active:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    evt.is_active = False
    db.add(evt)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------- Exceptions (single-occurrence) ---------------------------

@router.post("/events/{event_id}/exceptions:cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel_occurrence(event_id: uuid.UUID, payload: _InstanceRef, db: Session = Depends(get_db)) -> Response:
    evt: Optional[CalendarEvent] = db.get(CalendarEvent, event_id)
    if not evt or not evt.is_active:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # Avoid duplicates by UTC second
    new_ts = int(_utc(payload.instance_start_at).replace(microsecond=0).timestamp())
    existing = {int(_utc(x).replace(microsecond=0).timestamp()) for x in (evt.exdates or [])}
    if new_ts not in existing:
        evt.exdates = (evt.exdates or []) + [payload.instance_start_at]
        db.add(evt)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/events/{event_id}/exceptions:edit", response_model=CalendarEventRead, status_code=status.HTTP_201_CREATED)
def edit_occurrence(event_id: uuid.UUID, payload: _InstanceEdit, db: Session = Depends(get_db)) -> CalendarEventRead:
    evt: Optional[CalendarEvent] = db.get(CalendarEvent, event_id)
    if not evt or not evt.is_active:
        raise HTTPException(status_code=404, detail="Event not found")

    # 1) Cancel the original occurrence
    cancel_occurrence(event_id, _InstanceRef(instance_start_at=payload.instance_start_at), db)

    # 2) Create a one-off event with overrides
    duration = evt.end_at - evt.start_at
    base_tz = _event_tz(payload.timezone or evt.timezone, payload.instance_start_at)

    new_start = payload.start_at or payload.instance_start_at
    new_end = payload.end_at or (new_start + duration)

    # If explicitly all-day, normalize to local date 00:00..+1d
    override_all_day = payload.all_day if payload.all_day is not None else evt.all_day
    if override_all_day:
        local_start = new_start.astimezone(base_tz).replace(hour=0, minute=0, second=0, microsecond=0)
        new_start = local_start
        new_end = local_start + timedelta(days=1)

    new_evt = CalendarEvent(
        title=payload.title or evt.title,
        description=payload.description if payload.description is not None else evt.description,
        location=payload.location if payload.location is not None else evt.location,
        start_at=new_start,
        end_at=new_end,
        all_day=bool(override_all_day),
        timezone=(payload.timezone or evt.timezone),
        rrule=None,
        exdates=[],
        is_active=True,
    )
    db.add(new_evt)
    db.commit()
    db.refresh(new_evt)
    return new_evt


# --------------------------- Queries ---------------------------

@router.get("/events")
def list_events(
    start: Optional[datetime] = Query(None, description="ISO datetime with timezone, e.g. 2025-08-09T09:00:00+08:00"),
    end: Optional[datetime] = Query(None, description="ISO datetime with timezone"),
    include_inactive: bool = Query(False),
    expand: bool = Query(True, description="Expand recurrence into concrete occurrences"),
    db: Session = Depends(get_db),
):
    if start and (start.tzinfo is None or start.tzinfo.utcoffset(start) is None):
        raise HTTPException(status_code=400, detail="start must be timezone-aware")
    if end and (end.tzinfo is None or end.tzinfo.utcoffset(end) is None):
        raise HTTPException(status_code=400, detail="end must be timezone-aware")

    if not start or not end:
        start, end = _default_range(start or None)

    filters = []
    if not include_inactive:
        filters.append(CalendarEvent.is_active.is_(True))

    overlap = and_(CalendarEvent.start_at <= end, CalendarEvent.end_at >= start)
    recurs = CalendarEvent.rrule.is_not(None)
    filters.append(or_(overlap, recurs))

    events = db.execute(select(CalendarEvent).where(and_(*filters))).scalars().all()

    if not expand:
        return [CalendarEventRead.model_validate(e) for e in events]

    occs: List[CalendarOccurrenceRead] = []
    for e in events:
        occs.extend(_expand_event(e, start, end))
    occs.sort(key=lambda o: o.start_at)
    return occs


# --------------------------- Free/Busy ---------------------------

@router.get("/freebusy")
def freebusy(
    start: Optional[datetime] = Query(None, description="ISO datetime with timezone"),
    end: Optional[datetime] = Query(None, description="ISO datetime with timezone"),
    db: Session = Depends(get_db),
):
    if not start or not end:
        start, end = _default_range(start or None)

    filters = [CalendarEvent.is_active.is_(True)]
    overlap = and_(CalendarEvent.start_at <= end, CalendarEvent.end_at >= start)
    recurs = CalendarEvent.rrule.is_not(None)
    filters.append(or_(overlap, recurs))
    events = db.execute(select(CalendarEvent).where(and_(*filters))).scalars().all()

    # Expand and collect intervals (UTC for merge)
    occs: List[CalendarOccurrenceRead] = []
    for e in events:
        occs.extend(_expand_event(e, start, end))

    intervals = sorted([(_utc(o.start_at), _utc(o.end_at)) for o in occs], key=lambda x: x[0])
    merged: List[List[datetime]] = []
    for s, e in intervals:
        if not merged or s > merged[-1][1]:
            merged.append([s, e])
        else:
            if e > merged[-1][1]:
                merged[-1][1] = e

    return {
        "busy": [
            {
                "start": s.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "end": e.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            }
            for s, e in merged
        ]
    }


# --------------------------- ICS Export ---------------------------

@router.get("/ics")
def export_ics(
    start: Optional[datetime] = Query(None, description="ISO datetime with timezone, default now"),
    end: Optional[datetime] = Query(None, description="ISO datetime with timezone, default now+30d"),
    db: Session = Depends(get_db),
):
    """Export expanded occurrences as VCALENDAR. All-day events use VALUE=DATE in the event's timezone."""
    if not start or not end:
        start, end = _default_range(start or None)

    filters = [CalendarEvent.is_active.is_(True)]
    overlap = and_(CalendarEvent.start_at <= end, CalendarEvent.end_at >= start)
    recurs = CalendarEvent.rrule.is_not(None)
    filters.append(or_(overlap, recurs))
    events = db.execute(select(CalendarEvent).where(and_(*filters))).scalars().all()

    occs: List[CalendarOccurrenceRead] = []
    for e in events:
        occs.extend(_expand_event(e, start, end))
    occs.sort(key=lambda o: o.start_at)

    now_utc = datetime.now(timezone.utc)
    lines: List[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ClearKeep//Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:ClearKeep Calendar",
    ]

    for o in occs:
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{o.event_id}-{int(_utc(o.start_at).timestamp())}@clearkeep")
        lines.append(f"DTSTAMP:{_format_ics_dt(now_utc)}")

        base = next((e for e in events if e.id == o.event_id), None)
        is_all_day = bool(base and base.all_day)

        if is_all_day:
            tz = _event_tz(base.timezone if base else None, o.start_at)
            start_local = o.start_at.astimezone(tz)
            end_local = o.end_at.astimezone(tz)  # exclusive end at 00:00 local next day

            lines.append(f"DTSTART;VALUE=DATE:{start_local.date().strftime('%Y%m%d')}")
            lines.append(f"DTEND;VALUE=DATE:{end_local.date().strftime('%Y%m%d')}")
        else:
            lines.append(f"DTSTART:{_format_ics_dt(o.start_at)}")
            lines.append(f"DTEND:{_format_ics_dt(o.end_at)}")

        lines.append(f"SUMMARY:{_sanitize_ics_text(o.title)}")
        if base:
            if base.location:
                lines.append(f"LOCATION:{_sanitize_ics_text(base.location)}")
            if base.description:
                lines.append(f"DESCRIPTION:{_sanitize_ics_text(base.description)}")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    ics_text = "\r\n".join(lines) + "\r\n"

    def _fname(dt: datetime) -> str:
        return _utc(dt).strftime("%Y%m%dT%H%M%SZ")

    filename = f"ck_calendar_{_fname(start)}_{_fname(end)}.ics"
    headers = {"Content-Disposition": f'attachment; filename=\"{filename}\"'}
    return Response(content=ics_text, media_type="text/calendar", headers=headers)


# --------------------------- ICS Import (with TZ patch) ---------------------------

@router.post("/import", response_model=List[CalendarEventRead], status_code=status.HTTP_201_CREATED)
async def import_ics(
    file: UploadFile = File(...),
    default_timezone: Optional[str] = Query("Asia/Manila"),
    db: Session = Depends(get_db),
):
    """
    Import .ics:
      - All-day (DATE) → start at 00:00 local, end exclusive next day.
      - Timed (Z/UTC) → if default_timezone provided and not UTC, convert to that tz
        and store timezone field accordingly (e.g., Asia/Manila).
    """
    try:
        import icalendar as _ical
    except Exception:
        raise HTTPException(
            status_code=501,
            detail="ICS import requires the 'icalendar' package. Please install it in the server environment.",
        )

    content = await file.read()
    try:
        cal = _ical.Calendar.from_ical(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid ICS file: {e}")

    created: List[CalendarEvent] = []
    for ve in cal.walk("VEVENT"):
        # DTSTART / DTEND
        dtstart_prop = ve.get("DTSTART")
        if not dtstart_prop:
            continue
        dtend_prop = ve.get("DTEND")

        dtstart_val = dtstart_prop.dt
        dtend_val = dtend_prop.dt if dtend_prop else None
        tzid = None
        try:
            tzid = (dtstart_prop.params.get("TZID") if hasattr(dtstart_prop, "params") else None)
        except Exception:
            tzid = None

        # Determine event tz
        tz = None
        if tzid:
            tz = _event_tz(tzid, datetime.now(timezone.utc))
        else:
            if isinstance(dtstart_val, datetime) and dtstart_val.tzinfo:
                tz = dtstart_val.tzinfo
            else:
                tz = _event_tz(default_timezone, datetime.now(timezone.utc))

        # All-day vs timed
        if isinstance(dtstart_val, _date) and not isinstance(dtstart_val, datetime):
            all_day = True
            start_at = datetime(dtstart_val.year, dtstart_val.month, dtstart_val.day, tzinfo=tz)
            if isinstance(dtend_val, _date) and not isinstance(dtend_val, datetime):
                end_at = datetime(dtend_val.year, dtend_val.month, dtend_val.day, tzinfo=tz)
            else:
                end_at = start_at + timedelta(days=1)
        else:
            all_day = False
            start_at = dtstart_val if isinstance(dtstart_val, datetime) else datetime.combine(dtstart_val, datetime.min.time(), tz)
            if start_at.tzinfo is None:
                start_at = start_at.replace(tzinfo=tz)
            if isinstance(dtend_val, datetime):
                end_at = dtend_val if dtend_val.tzinfo else dtend_val.replace(tzinfo=tz)
            else:
                end_at = start_at + timedelta(hours=1)

            # TZ patch: if incoming is UTC/Z and default_timezone is set, convert to default tz
            current_tz_name = (getattr(start_at.tzinfo, "key", "") or getattr(start_at.tzinfo, "zone", "") or "UTC").upper()
            if default_timezone and current_tz_name == "UTC":
                new_tz = _event_tz(default_timezone, start_at)
                start_at = start_at.astimezone(new_tz)
                end_at = end_at.astimezone(new_tz)
                tz = new_tz  # use this for exdates and persisted timezone

        # Strings
        title = str(ve.get("SUMMARY", "Untitled"))
        description = str(ve.get("DESCRIPTION", ""))
        location = str(ve.get("LOCATION", ""))

        # RRULE
        rrule_val = ve.get("RRULE")
        rrule_text = None
        if rrule_val:
            try:
                rrule_text = _rrule_dict_to_text({k: v for k, v in rrule_val.items()})
            except Exception:
                rrule_text = None

        # EXDATE(s)
        exdates: List[datetime] = []
        raw_ex = ve.get("EXDATE")
        if raw_ex:
            if not isinstance(raw_ex, list):
                raw_ex = [raw_ex]
            for ex in raw_ex:
                dts = getattr(ex, "dts", None)
                if dts:
                    for v in dts:
                        dtv = v.dt
                        if isinstance(dtv, _date) and not isinstance(dtv, datetime):
                            exdates.append(datetime(dtv.year, dtv.month, dtv.day, tzinfo=tz))
                        else:
                            if isinstance(dtv, datetime):
                                if dtv.tzinfo is None:
                                    dtv = dtv.replace(tzinfo=tz)
                                # Convert UTC exdates to default tz as well (to match start_at base)
                                current_ex_tz = (getattr(dtv.tzinfo, "key", "") or getattr(dtv.tzinfo, "zone", "") or "UTC").upper()
                                if default_timezone and current_ex_tz == "UTC":
                                    dtv = dtv.astimezone(tz)
                                exdates.append(dtv)

        # Persisted timezone label
        tzname = _tzname_from_tzinfo(tz) or default_timezone or "UTC"

        evt = CalendarEvent(
            title=title,
            description=description,
            location=location,
            start_at=start_at,
            end_at=end_at,
            all_day=all_day,
            timezone=tzname,
            rrule=rrule_text,
            exdates=exdates,
            is_active=True,
        )
        db.add(evt)
        created.append(evt)

    if created:
        db.commit()
        for e in created:
            db.refresh(e)

    return created
