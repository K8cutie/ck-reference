import os
from datetime import datetime, timedelta, timezone
import requests
import pytest

BASE = os.getenv("BASE_URL", "http://127.0.0.1:8000")
TZ = timezone(timedelta(hours=8))  # Asia/Manila (+08:00)
def iso(dt): return dt.astimezone(TZ).replace(microsecond=0).isoformat()

def _server_up() -> bool:
    try:
        now = datetime.now(TZ)
        r = requests.get(f"{BASE}/calendar/ics", params={"start": iso(now), "end": iso(now + timedelta(days=1))}, timeout=4)
        return r.status_code == 200
    except Exception:
        return False

skip_if_down = pytest.mark.skipif(not _server_up(), reason="API server not running at BASE_URL")

@skip_if_down
def test_recurring_with_exdate():
    # Next Sunday 18:00–20:00 (local)
    now = datetime.now(TZ)
    days_ahead = (6 - now.weekday()) % 7 or 7  # Python: Mon=0..Sun=6
    start = (now + timedelta(days=days_ahead)).replace(hour=18, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=2)
    exdate = start + timedelta(days=14)

    payload = {
        "title": "PYTEST Recurring",
        "description": "weekly",
        "location": "Room 2",
        "start_at": iso(start),
        "end_at": iso(end),
        "all_day": False,
        "timezone": "Asia/Manila",
        "rrule": "FREQ=WEEKLY;BYDAY=SU",
        "exdates": [iso(exdate)],
        "is_active": True,
    }
    r = requests.post(f"{BASE}/calendar/events", json=payload); r.raise_for_status()
    ev_id = r.json()["id"]

    try:
        params = {
            "start": iso(now - timedelta(days=1)),
            "end": iso(now + timedelta(days=35)),
            "expand": "true",
        }
        r = requests.get(f"{BASE}/calendar/events", params=params); r.raise_for_status()
        occs = r.json()
        ours = [o for o in occs if o["title"] == "PYTEST Recurring"]
        assert len(ours) >= 2, "Expected at least two weekly occurrences"

        ex_utc = exdate.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
        starts = [o["start_at"] for o in ours]
        assert ex_utc not in starts, f"Exdate {ex_utc} still present"
    finally:
        requests.delete(f"{BASE}/calendar/events/{ev_id}")

@skip_if_down
def test_all_day_event_export_ics():
    # All-day tomorrow
    today = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    start = today + timedelta(days=2)
    end = start + timedelta(days=1)  # exclusive next-day
    payload = {
        "title": "PYTEST All-day",
        "description": "allday",
        "location": "Hall A",
        "start_at": iso(start),
        "end_at": iso(end),
        "all_day": True,
        "timezone": "Asia/Manila",
        "rrule": None,
        "exdates": [],
        "is_active": True,
    }
    r = requests.post(f"{BASE}/calendar/events", json=payload); r.raise_for_status()
    ev_id = r.json()["id"]

    try:
        params = {"start": iso(start - timedelta(days=1)), "end": iso(end + timedelta(days=1))}
        r = requests.get(f"{BASE}/calendar/ics", params=params); r.raise_for_status()
        ics = r.text

        ymd_start = start.date().strftime("%Y%m%d")
        ymd_end = end.date().strftime("%Y%m%d")

        assert "SUMMARY:PYTEST All-day" in ics
        assert f"DTSTART;VALUE=DATE:{ymd_start}" in ics
        assert f"DTEND;VALUE=DATE:{ymd_end}" in ics
    finally:
        requests.delete(f"{BASE}/calendar/events/{ev_id}")
