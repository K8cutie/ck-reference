# app/services/gl_accounting.py
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional
import json

from sqlalchemy import select, func, text, and_, or_
from sqlalchemy.orm import Session

from app.models.gl_accounting import (
    GLAccount,
    JournalEntry,
    JournalLine,
    AuditLog,
)

# Extracted modules
from app.services.gl.books import fetch_books_view
from app.services.gl.locks import _first_of_month, _is_period_locked, _set_period_lock
from app.services.gl.journal import (
    create_journal_entry,
    post_journal_entry,
    unpost_journal_entry,
    reverse_journal_entry,
)
from app.services.gl.accounts import (
    get_gl_account,
    get_gl_account_by_code,
    list_gl_accounts,
    create_gl_account,
    update_gl_account,
)
from app.services.gl.periods import (
    close_period,
    reopen_period,
    reclose_period,
)

# ----------------------------
# Journal listing (kept here)
# ----------------------------

def list_journal_entries(
    db: Session,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    reference_no: Optional[str] = None,
    source_module: Optional[str] = None,
    is_locked: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[JournalEntry]:
    stmt = select(JournalEntry).order_by(
        JournalEntry.entry_date.asc(), JournalEntry.entry_no.asc()
    )

    if date_from:
        stmt = stmt.where(JournalEntry.entry_date >= date_from)
    if date_to:
        stmt = stmt.where(JournalEntry.entry_date <= date_to)
    if reference_no:
        stmt = stmt.where(JournalEntry.reference_no == reference_no)
    if source_module:
        stmt = stmt.where(JournalEntry.source_module == source_module)
    if is_locked is not None:
        stmt = stmt.where(JournalEntry.is_locked.is_(is_locked))

    stmt = stmt.limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().unique().all())

# ----------------------------
# Internal audit log helper
# ----------------------------

def _log(
    db: Session,
    entity_type: str,
    entity_id: str,
    action: str,
    details: dict | None = None,
) -> None:
    try:
        db.add(
            AuditLog(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                details=json.dumps(details or {}),
                created_at=datetime.utcnow(),
            )
        )
        db.flush()
    except Exception:
        # audit must never block the business op
        db.rollback()
