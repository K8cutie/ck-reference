# app/services/gl_accounting.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Iterable, List, Optional

import json
from sqlalchemy import select, func, text, and_, or_
from sqlalchemy.orm import Session

from app.models.gl_accounting import (
    GLAccount,
    JournalEntry,
    JournalLine,
    AuditLog,
)

# ----------------------------
# Accounts (Chart of Accounts)
# ----------------------------

def get_gl_account(db: Session, account_id: int) -> Optional[GLAccount]:
    return db.get(GLAccount, account_id)

def get_gl_account_by_code(db: Session, code: str) -> Optional[GLAccount]:
    return db.execute(
        select(GLAccount).where(func.lower(GLAccount.code) == func.lower(code))
    ).scalar_one_or_none()

def list_gl_accounts(
    db: Session,
    q: Optional[str] = None,
    type_: Optional[str] = None,
    is_active: Optional[bool] = None,
    is_cash: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[GLAccount]:
    stmt = select(GLAccount).order_by(GLAccount.code.asc())
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(GLAccount.code).like(like),
                func.lower(GLAccount.name).like(like),
            )
        )
    if type_:
        stmt = stmt.where(GLAccount.type == type_)
    if is_active is not None:
        stmt = stmt.where(GLAccount.is_active.is_(is_active))
    if is_cash is not None:
        stmt = stmt.where(GLAccount.is_cash.is_(is_cash))
    stmt = stmt.limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())

def create_gl_account(
    db: Session,
    *,
    code: str,
    name: str,
    type_: str,
    normal_side: str,
    is_cash: bool = False,
    description: Optional[str] = None,
) -> GLAccount:
    # Uniqueness guards
    if get_gl_account_by_code(db, code):
        raise ValueError(f"GL account code already exists: {code}")
    name_exists = db.execute(
        select(GLAccount.id).where(func.lower(GLAccount.name) == func.lower(name))
    ).first()
    if name_exists:
        raise ValueError(f"GL account name already exists: {name}")

    acct = GLAccount(
        code=code,
        name=name,
        type=type_,
        normal_side=normal_side,
        is_cash=is_cash,
        description=description,
    )
    db.add(acct)
    db.flush()  # get id
    _log(db, "gl_account", str(acct.id), "create", {"code": code})
    db.commit()
    db.refresh(acct)
    return acct

def update_gl_account(
    db: Session,
    account_id: int,
    *,
    code: Optional[str] = None,
    name: Optional[str] = None,
    type_: Optional[str] = None,
    normal_side: Optional[str] = None,
    is_cash: Optional[bool] = None,
    description: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> GLAccount:
    acct = get_gl_account(db, account_id)
    if not acct:
        raise ValueError("GL account not found")

    if code and code != acct.code:
        if get_gl_account_by_code(db, code):
            raise ValueError(f"GL account code already exists: {code}")
        acct.code = code
    if name and name != acct.name:
        name_exists = db.execute(
            select(GLAccount.id).where(
                and_(
                    func.lower(GLAccount.name) == func.lower(name),
                    GLAccount.id != acct.id,
                )
            )
        ).first()
        if name_exists:
            raise ValueError(f"GL account name already exists: {name}")
        acct.name = name
    if type_:
        acct.type = type_
    if normal_side:
        acct.normal_side = normal_side
    if is_cash is not None:
        acct.is_cash = is_cash
    if description is not None:
        acct.description = description
    if is_active is not None:
        acct.is_active = is_active

    _log(db, "gl_account", str(acct.id), "update", {"code": acct.code})
    db.commit()
    db.refresh(acct)
    return acct


# ----------------------------
# Journal Entries & Lines
# ----------------------------

def get_journal_entry(db: Session, je_id: int) -> Optional[JournalEntry]:
    return db.get(JournalEntry, je_id)

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
    stmt = select(JournalEntry).order_by(JournalEntry.entry_date.asc(), JournalEntry.entry_no.asc())

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

def create_journal_entry(
    db: Session,
    *,
    entry_date: date,
    memo: Optional[str],
    currency_code: str,
    reference_no: Optional[str],
    source_module: Optional[str],
    source_id: Optional[str],
    lines: Iterable[dict],
    created_by_user_id: Optional[int] = None,
) -> JournalEntry:
    # Validate lines exist & accounts exist
    line_objs: List[JournalLine] = []
    total_debits = Decimal("0.00")
    total_credits = Decimal("0.00")
    next_line_no = 1

    for ln in lines:
        acct_id = int(ln["account_id"])
        acct = get_gl_account(db, acct_id)
        if not acct:
            raise ValueError(f"GL account not found: {acct_id}")

        debit = Decimal(str(ln.get("debit", "0") or "0"))
        credit = Decimal(str(ln.get("credit", "0") or "0"))

        # one-side-only rule
        if not ((debit > 0 and credit == 0) or (credit > 0 and debit == 0)):
            raise ValueError("Each line must have either a positive debit or a positive credit, not both or neither.")

        total_debits += debit
        total_credits += credit

        line_objs.append(
            JournalLine(
                account_id=acct.id,
                description=(ln.get("description") or None),
                debit=debit,
                credit=credit,
                line_no=int(ln.get("line_no") or next_line_no),
            )
        )
        next_line_no += 1

    if (total_debits - total_credits).quantize(Decimal("0.01")) != Decimal("0.00"):
        raise ValueError("Entry not balanced (total debits != total credits).")

    je = JournalEntry(
        entry_date=entry_date,
        memo=memo,
        currency_code=currency_code or "PHP",
        reference_no=reference_no,
        source_module=source_module,
        source_id=source_id,
        created_by_user_id=created_by_user_id,
        is_locked=False,
    )
    db.add(je)
    db.flush()  # get je.id and je.entry_no

    for ln in line_objs:
        ln.entry_id = je.id
        db.add(ln)

    _log(db, "journal_entry", str(je.id), "create", {"entry_no": int(je.entry_no or 0)})
    db.commit()
    db.refresh(je)
    return je

def post_journal_entry(
    db: Session,
    je_id: int,
    *,
    posted_by_user_id: Optional[int] = None,
) -> JournalEntry:
    je = get_journal_entry(db, je_id)
    if not je:
        raise ValueError("Journal entry not found.")
    if je.is_locked:
        return je  # already posted/locked

    # enforce balanced before posting
    total_debits = sum((ln.debit or 0) for ln in je.lines)
    total_credits = sum((ln.credit or 0) for ln in je.lines)
    if round(float(total_debits) - float(total_credits), 2) != 0.0:
        raise ValueError("Cannot post unbalanced journal entry.")

    now = datetime.utcnow()
    je.posted_at = now
    je.posted_by_user_id = posted_by_user_id
    je.is_locked = True
    je.locked_at = now

    _log(db, "journal_entry", str(je.id), "post", {"entry_no": int(je.entry_no or 0)})
    db.commit()
    db.refresh(je)
    return je


# ----------------------------
# Books (views) helpers
# ----------------------------

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
    """Return rows from one of the BIR books views as list[dict]."""
    if view_key not in BOOK_VIEWS:
        raise ValueError(f"Unknown books view: {view_key}")
    view_name = BOOK_VIEWS[view_key]

    # All views expose a 'date' column; apply range if provided
    where = []
    params = {}
    if date_from:
        where.append("date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        where.append("date <= :date_to")
        params["date_to"] = date_to

    sql = f"SELECT * FROM {view_name}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    # Stable sort
    if view_key in ("general_journal", "cash_receipts_book", "cash_disbursements_book"):
        sql += " ORDER BY date, reference"
    elif view_key == "general_ledger":
        sql += " ORDER BY account_code, date, reference"

    result = db.execute(text(sql), params)
    return [dict(row._mapping) for row in result]


# ----------------------------
# Internal audit log helper
# ----------------------------

def _log(db: Session, entity_type: str, entity_id: str, action: str, details: dict | None = None) -> None:
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
