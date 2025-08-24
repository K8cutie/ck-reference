# app/services/calendar_linker.py
from __future__ import annotations

import uuid
from datetime import datetime, time, timedelta
from typing import Any, Dict, Optional

from zoneinfo import ZoneInfo
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.calendar import CalendarEvent


DEFAULT_TZ = "Asia/Manila"
DEFAULT_START = time(10, 0)  # 10:00
DEFAULT_END = time(11, 0)    # 11:00


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _norm_type(sac_type: Any) -> str:
    """Return uppercase sacrament type (ORM enum or string)."""
    if hasattr(sac_type, "value"):
        return str(sac_type.value).upper()
    return str(sac_type).upper()


def _label_for_type(sac_type_u: str) -> str:
    """Human label for sacrament type."""
    return {
        "BAPTISM": "Baptism",
        "CONFIRMATION": "Confirmation",
        "MARRIAGE": "Marriage",
        "DEATH": "Funeral",
        "FUNERAL": "Funeral",
    }.get(sac_type_u, sac_type_u.title())


def _person_from_details(t: str, d: Dict[str, Any]) -> Optional[str]:
    """Try to extract a meaningful name to display in the title."""
    t = t.upper()
    if t == "CONFIRMATION":
        return d.get("confirmand") or d.get("candidate") or d.get("name")
    if t == "BAPTISM":
        return d.get("child_name") or d.get("baptismal_name") or d.get("name")
    if t == "MARRIAGE":
        groom = d.get("groom")
        bride = d.get("bride")
        if groom and bride:
            return f"{groom} & {bride}"
        return groom or bride
    if t in ("DEATH", "FUNERAL"):
        return d.get("deceased") or d.get("name")
    return d.get("name")


def _try_parse_time(s: str) -> Optional[time]:
    """Parse a flexible time string like '10:00', '10am', '10:30 PM'."""
    if not s:
        return None
    s = str(s).strip().upper().replace(".", "")
    fmts = ["%H:%M", "%H:%M:%S", "%I:%M %p", "%I %p"]
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            return time(dt.hour, dt.minute, dt.second)
        except ValueError:
            continue
    return None


def _extract_times(d: Dict[str, Any]) -> tuple[time, time]:
    """
    Derive start/end times from details dict.
    Supports:
      - time / start_time / schedule_time (e.g., "10:00", "2 PM")
      - end_time
      - start_at / end_at (ISO datetime strings) — times are taken from them
      - duration_minutes => end = start + minutes
    Falls back to 10:00–11:00 if missing.
    """
    # direct ISO hints
    if isinstance(d.get("start_at"), str):
        try:
            iso = d["start_at"].replace("Z", "+00:00")
            t0 = datetime.fromisoformat(iso).time()
            t1 = _try_parse_time(d.get("end_time", "")) or DEFAULT_END
            return t0, t1
        except Exception:
            pass
    if isinstance(d.get("end_at"), str):
        try:
            iso = d["end_at"].replace("Z", "+00:00")
            t1 = datetime.fromisoformat(iso).time()
            t0 = _try_parse_time(d.get("start_time", "")) or _try_parse_time(d.get("time", "")) or DEFAULT_START
            return t0, t1
        except Exception:
            pass

    # common keys
    start = (
        _try_parse_time(d.get("start_time", "")) or
        _try_parse_time(d.get("schedule_time", "")) or
        _try_parse_time(d.get("time", "")) or
        DEFAULT_START
    )
    if "end_time" in d and d["end_time"]:
        end = _try_parse_time(d["end_time"]) or DEFAULT_END
    elif isinstance(d.get("duration_minutes"), (int, float)) and d["duration_minutes"] > 0:
        dt = datetime.combine(datetime.today().date(), start)
        dt_end = dt + timedelta(minutes=int(d["duration_minutes"]))
        end = dt_end.time()
    else:
        end = DEFAULT_END
    return start, end


def _build_title(sac_row: Any) -> str:
    t_u = _norm_type(getattr(sac_row, "type", ""))
    label = _label_for_type(t_u)
    details = getattr(sac_row, "details", {}) or {}
    person = _person_from_details(t_u, details)
    return f"{label} – {person}" if person else label


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def upsert_calendar_event_for_sacrament(
    db: Session,
    sac_row: Any,
    *,
    tzname: str = DEFAULT_TZ,
) -> CalendarEvent:
    """
    Ensure a CalendarEvent exists and reflects the sacrament schedule.
    - origin: 'sacrament'
    - external_ref: 'SAC-<id>'
    - NO payment details are copied.
    """
    sac_id = getattr(sac_row, "id", None)
    if not sac_id:
        raise ValueError("sacrament row must have an id")

    details: Dict[str, Any] = getattr(sac_row, "details", {}) or {}
    t_u = _norm_type(getattr(sac_row, "type", ""))
    title = _build_title(sac_row)

    # date + times
    sac_date = getattr(sac_row, "date", None)
    if sac_date is None:
        raise ValueError("sacrament row must have a date")
    start_t, end_t = _extract_times(details)
    tz = ZoneInfo(tzname)
    start_at = datetime.combine(sac_date, start_t).replace(tzinfo=tz)
    end_at = datetime.combine(sac_date, end_t).replace(tzinfo=tz)

    # lookup existing by (origin, external_ref)
    external_ref = f"SAC-{sac_id}"
    existing = db.execute(
        select(CalendarEvent).where(
            and_(
                CalendarEvent.origin == "sacrament",
                CalendarEvent.external_ref == external_ref,
            )
        )
    ).scalars().first()

    if existing is None:
        ev = CalendarEvent(
            id=uuid.uuid4(),
            title=title,
            description=None,  # no payment info
            location=details.get("location"),
            start_at=start_at,
            end_at=end_at,
            all_day=False,
            timezone=tzname,
            rrule=None,
            exdates=[],  # ensure non-null
            is_active=True,
        )
        ev.origin = "sacrament"
        ev.external_ref = external_ref
        ev.meta = {
            "sacrament_id": sac_id,
            "sacrament_type": t_u,
            "parishioner_id": getattr(sac_row, "parishioner_id", None),
        }
        db.add(ev)
        db.flush()
        return ev

    # update existing
    existing.title = title
    existing.location = details.get("location", existing.location)
    existing.start_at = start_at
    existing.end_at = end_at
    existing.timezone = tzname
    existing.is_active = True
    meta = dict(existing.meta or {})
    meta.update(
        {
            "sacrament_id": sac_id,
            "sacrament_type": t_u,
            "parishioner_id": getattr(sac_row, "parishioner_id", None),
        }
    )
    existing.meta = meta
    db.flush()
    return existing
