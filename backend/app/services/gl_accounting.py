# app/services/gl_accounting.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Iterable, List, Optional
import json
import calendar  # for last day of month

from sqlalchemy import select, func, text, and_, or_
from sqlalchemy.orm import Session

from app.models.gl_accounting import (
    GLAccount,
    JournalEntry,
    JournalLine,
    AuditLog,
)

# ----------------------------
# Helpers for period locking
# ----------------------------

def _first_of_month(d: date) -> date:
    return date(d.year, d.month, 1)

def _is_period_locked(db: Session, d: date) -> bool:
    """
    True if the month containing 'd' is locked in gl_period_locks.
    Uses a lightweight raw SQL check (no ORM model required).
    """
    sql = text(
        """
        SELECT is_locked
        FROM gl_period_locks
        WHERE period_month = :period_month
        LIMIT 1
        """
    )
    row = db.execute(sql, {"period_month": _first_of_month(d)}).first()
    return bool(row and row[0])

def _set_period_lock(db: Session, first: date, is_locked: bool, note: Optional[str] = None) -> None:
    sql = text(
        """
        INSERT INTO gl_period_locks (period_month, is_locked, note)
        VALUES (:pm, :locked, :note)
        ON CONFLICT (period_month)
        DO UPDATE SET is_locked = EXCLUDED.is_locked,
                      note      = COALESCE(EXCLUDED.note, gl_period_locks.note)
        """
    )
    db.execute(sql, {"pm": first, "locked": is_locked, "note": note})
    db.commit()


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
            raise ValueError(
                "Each line must have either a positive debit or a positive credit, not both or neither."
            )

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

    # Already posted/locked?
    if je.is_locked:
        return je

    # 🚫 Enforce month locks
    if _is_period_locked(db, je.entry_date):
        y_m = je.entry_date.strftime("%Y-%m")
        raise ValueError(f"Cannot post: period {y_m} is locked.")

    # Enforce balance before posting
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


def unpost_journal_entry(
    db: Session,
    je_id: int,
    *,
    unposted_by_user_id: Optional[int] = None,
) -> JournalEntry:
    """
    Make a posted JE draft again.
    Guardrails:
      - If the original entry month is locked, refuse.
      - Otherwise clear post flags and unlock.
    """
    je = get_journal_entry(db, je_id)
    if not je:
        raise ValueError("Journal entry not found.")

    if not je.is_locked:
        return je  # already draft

    # 🚫 Enforce month locks (cannot unpost in a locked period)
    if _is_period_locked(db, je.entry_date):
        y_m = je.entry_date.strftime("%Y-%m")
        raise ValueError(f"Cannot unpost: period {y_m} is locked.")

    je.posted_at = None
    je.posted_by_user_id = None
    je.is_locked = False
    je.locked_at = None

    _log(db, "journal_entry", str(je.id), "unpost", {"entry_no": int(je.entry_no or 0)})
    db.commit()
    db.refresh(je)
    return je


def reverse_journal_entry(
    db: Session,
    je_id: int,
    *,
    as_of: Optional[date] = None,
    created_by_user_id: Optional[int] = None,
) -> JournalEntry:
    """
    Create and post a reversing entry for a **posted** JE.
    - Reversal date defaults to the source JE's date unless `as_of` is provided.
    - Guardrails:
        * Source must be posted (locked).
        * Target reversal month must not be locked.
    """
    src = get_journal_entry(db, je_id)
    if not src:
        raise ValueError("Journal entry not found.")
    if not src.is_locked:
        raise ValueError("Cannot reverse a draft journal entry.")

    rev_date = as_of or src.entry_date
    if _is_period_locked(db, rev_date):
        y_m = rev_date.strftime("%Y-%m")
        raise ValueError(f"Cannot create reversal in locked period {y_m}.")

    # Build reversed lines (swap debit/credit)
    lines: List[dict] = []
    for ln in src.lines:
        debit = float(ln.credit or 0)
        credit = float(ln.debit or 0)
        lines.append(
            {
                "account_id": ln.account_id,
                "description": f"Reversal of JE {src.entry_no}",
                "debit": debit,
                "credit": credit,
            }
        )

    ref_base = src.reference_no or f"JE-{src.entry_no}"
    ref_rev = f"{ref_base}-REV"

    rev = create_journal_entry(
        db,
        entry_date=rev_date,
        memo=(src.memo or "") + " (reversal)",
        currency_code=src.currency_code or "PHP",
        reference_no=ref_rev,
        source_module="reversal",
        source_id=str(src.id),
        lines=lines,
        created_by_user_id=created_by_user_id,
    )

    # Post reversal (will re-check balance & lock)
    return post_journal_entry(db, rev.id, posted_by_user_id=created_by_user_id)


# ----------------------------
# Period Close / Reopen (services)
# ----------------------------

def close_period(
    db: Session,
    year: int,
    month: int,
    *,
    equity_account_id: int,
    note: Optional[str] = None,
    created_by_user_id: Optional[int] = None,
) -> JournalEntry:
    """
    Close Income/Expense accounts into Equity for the given (year, month).
    - Creates a single posted JE dated on the LAST day of the month with reference CLOSE-YYYYMM.
    - Debits each income account by its net credit; credits each expense account by its net debit.
    - Offsets the net to the provided Equity account (credit for income>expense, debit for loss).
    - Refuses if the period is locked or already has a posted closing JE.
    - Locks the month after posting.
    """
    first = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    last = date(year, month, last_day)

    if _is_period_locked(db, first):
        y_m = first.strftime("%Y-%m")
        raise ValueError(f"Cannot close: period {y_m} is locked.")

    ref = f"CLOSE-{year:04d}{month:02d}"
    existing = db.execute(
        select(JournalEntry).where(
            JournalEntry.reference_no == ref,
            JournalEntry.is_locked.is_(True),
        )
    ).scalar_one_or_none()
    if existing:
        raise ValueError(f"Already closed for {year}-{month:02d}.")

    # Aggregate posted activity for the month
    sql = text(
        """
        SELECT a.id AS account_id, a.type AS acct_type, a.code AS code, a.name AS name,
               COALESCE(SUM(l.debit),0) AS dr, COALESCE(SUM(l.credit),0) AS cr
        FROM journal_lines l
        JOIN journal_entries je ON je.id = l.entry_id
        JOIN gl_accounts a ON a.id = l.account_id
        WHERE je.is_locked = TRUE
          AND je.entry_date >= :first AND je.entry_date <= :last
        GROUP BY a.id, a.type, a.code, a.name
        """
    )
    rows = db.execute(sql, {"first": first, "last": last}).mappings().all()

    income_total = Decimal("0.00")
    expense_total = Decimal("0.00")
    lines: List[dict] = []

    for r in rows:
        acct_type = (r["acct_type"] or "").lower()
        dr = Decimal(str(r["dr"] or 0))
        cr = Decimal(str(r["cr"] or 0))
        if acct_type == "income":
            net_credit = cr - dr
            if net_credit > 0:
                lines.append({
                    "account_id": int(r["account_id"]),
                    "description": f"Close income {r['code']}",
                    "debit": float(net_credit),
                    "credit": 0.0,
                })
                income_total += net_credit
        elif acct_type == "expense":
            net_debit = dr - cr
            if net_debit > 0:
                lines.append({
                    "account_id": int(r["account_id"]),
                    "description": f"Close expense {r['code']}",
                    "debit": 0.0,
                    "credit": float(net_debit),
                })
                expense_total += net_debit

    # Nothing to close?
    if not lines and income_total == 0 and expense_total == 0:
        raise ValueError(f"Nothing to close for {year}-{month:02d}.")

    equity_amt = income_total - expense_total
    if equity_amt > 0:
        # Net income -> credit equity
        lines.append({
            "account_id": equity_account_id,
            "description": f"Close {year}-{month:02d} Net Income",
            "debit": 0.0,
            "credit": float(equity_amt),
        })
    elif equity_amt < 0:
        # Net loss -> debit equity
        lines.append({
            "account_id": equity_account_id,
            "description": f"Close {year}-{month:02d} Net Loss",
            "debit": float(-equity_amt),
            "credit": 0.0,
        })

    # Create & post the closing JE on the last day
    je = create_journal_entry(
        db,
        entry_date=last,
        memo=f"Closing Entry {year}-{month:02d}",
        currency_code="PHP",
        reference_no=ref,
        source_module="closing",
        source_id=ref,
        lines=lines,
        created_by_user_id=created_by_user_id,
    )
    je = post_journal_entry(db, je.id, posted_by_user_id=created_by_user_id)

    # Lock the period
    _set_period_lock(db, first, True, note or "closed")

    return je


def reopen_period(
    db: Session,
    year: int,
    month: int,
    *,
    note: Optional[str] = None,
) -> dict:
    """
    Reopen a previously locked period (does NOT reverse closing entries).
    """
    first = date(year, month, 1)
    _set_period_lock(db, first, False, note or "reopened")
    return {"period_month": first.isoformat(), "is_locked": False, "note": note or "reopened"}


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
