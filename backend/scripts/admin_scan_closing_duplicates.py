"""
Admin tool: scan (and optionally fix) duplicate posted closing entries CLOSE-YYYYMM.

Usage:
  (.venv) > python -m scripts.admin_scan_closing_duplicates
  (.venv) > python -m scripts.admin_scan_closing_duplicates --fix

Behavior:
- SCAN: lists months that have multiple posted closing JEs and/or any *older* closing
        without a posted reversal (source_module='reversal', source_id=<closing.id>).
  * Ignores reversal rows (CLOSE-YYYYMM-REV).
  * The **latest** closing per month is treated as canonical and does not
    require a reversal.
- FIX:  reopens the month, creates a posted reversal for each *older* closing
        that lacks one, then reports post-fix status.
"""

from __future__ import annotations
import argparse
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Tuple

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.gl_accounting import JournalEntry
from app.services.gl_accounting import reopen_period, reverse_journal_entry


@dataclass
class MonthStatus:
    ref: str                 # e.g., CLOSE-202508
    year: int
    month: int
    closing_ids: List[int]         # all posted closing JE ids for this month
    missing_reversal: List[int]    # subset of *older* closings missing a posted reversal
    latest_id: int                 # canonical closing id


def _last_dom(y: int, m: int) -> date:
    for d in (31, 30, 29, 28):
        try:
            return date(y, m, d)
        except ValueError:
            continue
    return date(y, m, 28)


def _has_posted_reversal_for(db: Session, closing_id: int) -> bool:
    c = db.execute(
        select(func.count()).select_from(JournalEntry).where(
            JournalEntry.source_module == "reversal",
            JournalEntry.source_id == str(closing_id),
            JournalEntry.is_locked.is_(True),
        )
    ).scalar()
    return bool(c and int(c) > 0)


def scan(db: Session) -> Dict[str, MonthStatus]:
    # Pull all posted CLOSE-* rows, then ignore those that are actually the *reversal* rows.
    rows = db.execute(
        select(JournalEntry.id, JournalEntry.reference_no, JournalEntry.entry_date)
        .where(JournalEntry.is_locked.is_(True))
        .where(JournalEntry.reference_no.like("CLOSE-%"))
        .order_by(JournalEntry.reference_no, JournalEntry.id.asc())
    ).all()

    # Group by the pure CLOSE-YYYYMM (drop -REV rows completely)
    by_ref: Dict[str, List[Tuple[int, date]]] = {}
    for je_id, ref, when in rows:
        if str(ref).endswith("-REV"):
            continue  # ignore reversal entries in the scan
        by_ref.setdefault(ref, []).append((int(je_id), when))

    result: Dict[str, MonthStatus] = {}
    for ref, items in by_ref.items():
        y = int(ref[6:10]); m = int(ref[10:12])
        ids_sorted = sorted(i for i, _ in items)
        latest = ids_sorted[-1]
        # Only *older* closings require reversals
        older_ids = [cid for cid in ids_sorted if cid != latest]
        missing = [cid for cid in older_ids if not _has_posted_reversal_for(db, cid)]

        # Only report months that still need work
        if len(ids_sorted) > 1 and missing:
            result[ref] = MonthStatus(
                ref=ref, year=y, month=m,
                closing_ids=ids_sorted,
                missing_reversal=missing,
                latest_id=latest,
            )
    return result


def fix(db: Session, months: Dict[str, MonthStatus]) -> tuple[int, int]:
    created = 0
    skipped = 0
    for ref, st in months.items():
        # Reopen month to allow creating reversals
        reopen_period(db, st.year, st.month, note="admin: fix duplicate closings")
        as_of = _last_dom(st.year, st.month)

        for cid in st.closing_ids:
            if cid == st.latest_id:
                continue  # never reverse the canonical latest closing
            if _has_posted_reversal_for(db, cid):
                skipped += 1
                continue
            reverse_journal_entry(db, cid, as_of=as_of, created_by_user_id=None)
            created += 1
    return created, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true", help="Create posted reversals for older closings that lack one")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        dup = scan(db)
        if not dup:
            print("✅ Scan OK: no duplicate closings missing reversals.")
            return 0

        print(f"⚠️  Found {len(dup)} month(s) with unresolved older closings:")
        for ref, st in sorted(dup.items()):
            print(f" - {ref}: closings={st.closing_ids} latest={st.latest_id} missing_reversal={st.missing_reversal}")

        if args.fix:
            created, skipped = fix(db, dup)
            print(f"🛠️  Fix applied: created {created} reversal(s), skipped {skipped} (already had reversal).")
            # Re-scan to confirm
            dup2 = scan(db)
            if dup2:
                print("❌ Still unresolved:")
                for ref, st in sorted(dup2.items()):
                    print(f" - {ref}: closings={st.closing_ids} latest={st.latest_id} missing_reversal={st.missing_reversal}")
                return 2
            print("✅ Post-fix OK: all months clean.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
