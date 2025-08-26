# Smoke: Journal sequence integrity (non-blocking)
# - Fails only if there are duplicate entry_no values among posted/draft JEs.
# - Reports gaps and monotonicity, but gaps DO NOT fail the smoke.

from __future__ import annotations
import os, sys, json
from collections import Counter
from typing import List, Dict, Any
import requests

BASE = os.getenv("BASE", "http://127.0.0.1:8000")

def req(m, path, ok=200, **kw):
    r = requests.request(m, f"{BASE}{path}", timeout=60, **kw)
    ct = r.headers.get("content-type","")
    body = r.json() if ct.startswith("application/json") else r.text
    if r.status_code != ok:
        raise SystemExit(f"{m} {path} -> {r.status_code}: {body}")
    return body

def fetch_all_journal(limit=200) -> List[Dict[str, Any]]:
    out, offset = [], 0
    while True:
        chunk = req("GET", "/gl/journal", params={"limit": limit, "offset": offset})
        if not chunk:
            break
        out.extend(chunk)
        if len(chunk) < limit:
            break
        offset += len(chunk)
    return out

def main():
    jes = fetch_all_journal()
    if not jes:
        print("✅ No journal entries yet; sequence trivially OK.")
        return

    # Collect entry_no (ignore None just in case)
    seq = [(int(je["entry_no"]), int(je["id"])) for je in jes if je.get("entry_no") is not None]
    seq.sort()  # by entry_no, then id

    entry_nos = [n for n, _ in seq]
    ids       = [i for _, i in seq]

    # Duplicates check (hard fail)
    dup = [n for n, c in Counter(entry_nos).items() if c > 1]
    if dup:
        detail = [ {"entry_no": n, "ids": [i for (n2,i) in seq if n2==n]} for n in dup ]
        raise SystemExit("❌ Duplicate entry_no detected:\n" + json.dumps(detail, indent=2))

    # Monotonic (non-decreasing) check (informational)
    monotonic = all(entry_nos[i] < entry_nos[i+1] for i in range(len(entry_nos)-1))

    # Gap count (informational)
    gaps = 0
    if entry_nos:
        expected = list(range(entry_nos[0], entry_nos[-1]+1))
        gaps = len(set(expected) - set(entry_nos))

    summary = {
        "count": len(entry_nos),
        "first_entry_no": entry_nos[0],
        "last_entry_no": entry_nos[-1],
        "monotonic_strict_increasing": monotonic,
        "gaps_between_first_and_last": gaps
    }
    print("✅ JOURNAL SEQUENCE OK")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        print(e, file=sys.stderr); sys.exit(1)
