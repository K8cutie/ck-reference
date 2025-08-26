from __future__ import annotations

from datetime import date
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

# Views used by Books of Accounts
BOOK_VIEWS = {
    "general_journal": "vw_general_journal",
    "general_ledger": "vw_general_ledger",
    "cash_receipts_book": "vw_cash_receipts_book",
    "cash_disbursements_book": "vw_cash_disbursements_book",
}

def fetch_books_view(
    db: Session,
    view_key: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[dict]:
    """
    Return rows from one of the BIR books views as list[dict].

    IMPORTANT: We only show **posted** entries. We inner-join each view to
    journal_entries on (reference_no, entry_date) and filter je.is_locked = TRUE.
    """
    if view_key not in BOOK_VIEWS:
        raise ValueError(f"Unknown books view: {view_key}")

    view_name = BOOK_VIEWS[view_key]

    where = ["je.is_locked = TRUE"]
    params: dict = {}

    if date_from:
        where.append("je.entry_date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        where.append("je.entry_date <= :date_to")
        params["date_to"] = date_to

    sql = f"""
        SELECT v.*
        FROM {view_name} v
        JOIN journal_entries je
          ON je.reference_no = v.reference
         AND je.entry_date   = v.date
        WHERE {" AND ".join(where)}
    """

    # Stable sort
    if view_key in ("general_journal", "cash_receipts_book", "cash_disbursements_book"):
        sql += " ORDER BY v.date, v.reference"
    elif view_key == "general_ledger":
        sql += " ORDER BY v.account_code, v.date, v.reference"

    result = db.execute(text(sql), params)
    return [dict(row._mapping) for row in result]
