from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.models.gl_accounting import GLAccount, AuditLog

def _log(
    db: Session,
    entity_type: str,
    entity_id: str,
    action: str,
    details: dict | None = None,
) -> None:
    """Audit helper — never block the operation."""
    try:
        db.add(
            AuditLog(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                details=None if details is None else str(details),
                created_at=datetime.utcnow(),
            )
        )
        db.flush()
    except Exception:
        db.rollback()

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
            func.lower(GLAccount.code).like(like) | func.lower(GLAccount.name).like(like)
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
    db.flush()  # assign id
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
