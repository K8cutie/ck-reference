# Minimal integration smoke test for Calendar Scope B
# Run:  python scripts/smoke_calendar.py
# If needed: pip install requests

import os, sys, time
from datetime import datetime, timedelta, timezone
import requests

BASE = os.getenv("BASE_URL", "http://127.0.0.1:8000")
TZ = timezone(timedelta(hours=8))  # Asia/Manila (+08:00)

def iso(dt): return dt.astimezone(TZ).replace(microsecond=0).isoformat()

def main():
    print(f"→ Using API {BASE}")

    # window = now..now+30d (Manila)
    now_local = datetime.now(TZ)
    win_start = (now_local - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    win_end   = (now_local + timedelta(days=30)).replace(hour=23, minute=59, second=59, microsecond=0)

    # 1) Create one-off
    one_start = (now_local + timedelta(days=2)).replace(hour=9, minute=0, second=0, microsecond=0)
    one_end   = one_start + timedelta(hours=1)
    one = {
        "title": "SMOKE One-off",
        "description": "smoke",
        "location": "Hall A",
        "start_at": iso(one_start),
        "end_at": iso(one_end),
        "all_day": False,
        "timezone": "Asia/Manila",
        "rrule": None,
        "exdates": [],
        "is_active": True,
    }
    r = requests.post(f"{BASE}/calendar/events", json=one); r.raise_for_status()
    one_id = r.json()["id"]
    print(f"✓ Created one-off {one_id}")

    # 2) Create weekly recurring with one exdate (skip 2 weeks from start)
    recur_start = (now_local + timedelta(days=3)).replace(hour=18, minute=0, second=0, microsecond=0)
    recur_end   = recur_start + timedelta(hours=2)
    exdate_local = recur_start + timedelta(days=14)
    recur = {
        "title": "SMOKE Weekly",
        "description": "smoke",
        "location": "Room 2",
        "start_at": iso(recur_start),
        "end_at": iso(recur_end),
        "all_day": False,
        "timezone": "Asia/Manila",
        "rrule": "FREQ=WEEKLY;BYDAY=SU",  # weekly on Sunday
        "exdates": [iso(exdate_local)],
        "is_active": True,
    }
    r = requests.post(f"{BASE}/calendar/events", json=recur); r.raise_for_status()
    recur_id = r.json()["id"]
    print(f"✓ Created recurring {recur_id} (exdate {iso(exdate_local)})")

    # 3) List expanded occurrences and verify exdate is excluded
    params = {
        "start": iso(win_start).replace("+08:00", "+08:00"),
        "end": iso(win_end).replace("+08:00", "+08:00"),
        "expand": "true",
    }
    r = requests.get(f"{BASE}/calendar/events", params=params); r.raise_for_status()
    occs = r.json()
    # Build the UTC-Z form for comparison (API returns Z)
    ex_utc = exdate_local.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    titles = [o["title"] for o in occs]
    starts = [o["start_at"] for o in occs]
    assert any("SMOKE Weekly" == t for t in titles), "No recurring occurrences returned"
    assert ex_utc not in starts, f"Exdate {ex_utc} still present in occurrences"
    print("✓ Recurrence expansion ok; exdate excluded")

    # 4) Export ICS for the window
    r = requests.get(f"{BASE}/calendar/ics", params=params); r.raise_for_status()
    assert "BEGIN:VCALENDAR" in r.text, "ICS export missing VCALENDAR"
    print("✓ ICS export ok")

    # 5) GET / PUT / DELETE for the one-off
    r = requests.get(f"{BASE}/calendar/events/{one_id}"); r.raise_for_status()
    # shift by +30 mins
    s2 = (one_start + timedelta(minutes=30))
    e2 = (one_end + timedelta(minutes=30))
    r = requests.put(f"{BASE}/calendar/events/{one_id}", json={"start_at": iso(s2), "end_at": iso(e2)}); r.raise_for_status()
    r = requests.delete(f"{BASE}/calendar/events/{one_id}"); assert r.status_code in (200,204), "Delete failed"
    print("✓ GET/PUT/DELETE ok")

    # cleanup recurring
    r = requests.delete(f"{BASE}/calendar/events/{recur_id}")
    print("✓ Cleanup ok")
    print("\nALL SMOKE TESTS PASSED ✅")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("❌ Smoke test failed:", e)
        sys.exit(1)
