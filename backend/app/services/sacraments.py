# app/services/sacraments.py
from __future__ import annotations

from datetime import datetime, time, timedelta, date as _date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

# Schemas
from app.schemas.sacrament import SacramentCreate, SacramentRead

# ORM models (singular path; fall back to plural if present)
try:
    from app.models.sacrament import Sacrament, SacramentType  # type: ignore
except Exception:  # pragma: no cover
    from app.models.sacraments import Sacrament, SacramentType  # type: ignore

from app.models.transactions import Transaction, TransactionType
from app.models.calendar_event import CalendarEvent


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def _norm_type(t: str | SacramentType) -> str:
    """Return canonical lower-case sacrament type, mapping aliases (e.g. 'funeral' -> 'death')."""
    if isinstance(t, SacramentType):
        t = t.name.lower()
    t = (t or "").strip().lower()
    if t == "funeral":
        return "death"
    return t


def _enum_type(t: str | SacramentType) -> SacramentType:
    nt = _norm_type(t)
    return SacramentType[nt.upper()]  # type: ignore[index]


def _label_for_type(t: str | SacramentType) -> str:
    nt = _norm_type(t)
    mapping = {
        "baptism": "Baptism",
        "confirmation": "Confirmation",
        "marriage": "Marriage",
        "death": "Funeral",
    }
    return mapping.get(nt, nt.title() or "Sacrament")


def _desc_for_tx(t: str | SacramentType) -> str:
    return f"{_label_for_type(t)} fee"


def _category_name_for_type(t: str | SacramentType) -> Optional[str]:
    nt = _norm_type(t)
    mapping = {
        "baptism": "Sacraments – Baptism",
        "confirmation": "Sacraments – Confirmation",
        "marriage": "Sacraments – Marriage",
        "death": "Sacraments – Funeral",
    }
    return mapping.get(nt)


def _to_float(x: Any) -> float:
    if x is None:
        return 0.0
    if isinstance(x, Decimal):
        return float(x)
    return float(x)


def _time_from_details(details: Dict[str, Any]) -> time:
    s = (details or {}).get("time") or (details or {}).get("start_time") or "10:00"
    try:
        hh, mm = s.split(":")
        return time(int(hh), int(mm))
    except Exception:
        return time(10, 0)


def _title_from_details(t: str | SacramentType, details: Dict[str, Any]) -> str:
    label = _label_for_type(t)
    name = (
        (details or {}).get("child_name")
        or (details or {}).get("confirmand")
        or (details or {}).get("couple")
        or (details or {}).get("deceased")
    )
    return f"{label}: {name}" if name else label


def _get_category_id(db: Session, name: Optional[str]) -> Optional[int]:
    if not name:
        return None
    row = db.execute(text("SELECT id FROM categories WHERE name=:n LIMIT 1"), {"n": name}).first()
    return int(row[0]) if row else None


# ─────────────────────────────────────────────────────────────────────────────
# Transaction <-> Sacrament sync
# ─────────────────────────────────────────────────────────────────────────────

def _sync_transaction_for_sacrament(db: Session, sac: Sacrament) -> None:
    """Create/update/remove the related Transaction for this sacrament (reference_no = SAC-{id})."""
    ref = f"SAC-{sac.id}"
    tx: Optional[Transaction] = (
        db.execute(select(Transaction).where(Transaction.reference_no == ref)).scalars().first()
    )

    fee = _to_float(getattr(sac, "fee", 0) or 0)
    if fee <= 0:
        if tx:
            db.delete(tx)
            db.commit()
        return

    desc = _desc_for_tx(sac.type)
    cat_id = _get_category_id(db, _category_name_for_type(sac.type))

    if tx:
        tx.date = sac.date
        tx.description = desc
        tx.amount = fee
        tx.type = TransactionType.income
        tx.category_id = cat_id
        tx.parishioner_id = sac.parishioner_id
        tx.payment_method = getattr(tx, "payment_method", "cash") or "cash"
    else:
        tx = Transaction(
            date=sac.date,
            description=desc,
            amount=fee,
            type=TransactionType.income,
            category_id=cat_id,
            parishioner_id=sac.parishioner_id,
            payment_method="cash",
            reference_no=ref,
        )
        db.add(tx)

    db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Calendar <-> Sacrament sync
# ─────────────────────────────────────────────────────────────────────────────

def _sync_calendar_for_sacrament(db: Session, sac: Sacrament) -> None:
    """
    Create/update a CalendarEvent for the sacrament.
    • Uses Asia/Manila time
    • Duration default 1 hour
    • No payment info is written to calendar description
    """
    details = getattr(sac, "details", {}) or {}
    notes = getattr(sac, "notes", None)
    location = details.get("location")

    tz = ZoneInfo("Asia/Manila")
    start_t = _time_from_details(details)
    start_at = datetime.combine(sac.date, start_t, tz)
    end_at = start_at + timedelta(hours=1)

    title = _title_from_details(sac.type, details)
    ref = f"SAC-{sac.id}"

    existing = (
        db.execute(
            select(CalendarEvent).where(
                CalendarEvent.external_ref == ref,
                CalendarEvent.is_active.is_(True),
            )
        )
        .scalars()
        .first()
    )

    if existing:
        existing.title = title
        existing.description = notes  # general notes only (no fees)
        existing.location = location
        existing.start_at = start_at
        existing.end_at = end_at
        existing.all_day = False
        existing.timezone = "Asia/Manila"
        existing.rrule = None
        existing.origin = "sacrament"
        existing.meta = {
            "sacrament_id": sac.id,
            "parishioner_id": sac.parishioner_id,
            "type": _norm_type(sac.type),
        }
    else:
        ev = CalendarEvent(
            title=title,
            description=notes,
            location=location,
            start_at=start_at,
            end_at=end_at,
            all_day=False,
            timezone="Asia/Manila",
            rrule=None,
            exdates=[],
            is_active=True,
            origin="sacrament",
            external_ref=ref,
            meta={
                "sacrament_id": sac.id,
                "parishioner_id": sac.parishioner_id,
                "type": _norm_type(sac.type),
            },
        )
        db.add(ev)

    db.commit()


def _deactivate_calendar_for_sacrament(db: Session, sac_id: int) -> None:
    ref = f"SAC-{sac_id}"
    ev = (
        db.execute(
            select(CalendarEvent).where(
                CalendarEvent.external_ref == ref,
                CalendarEvent.is_active.is_(True),
            )
        )
        .scalars()
        .first()
    )
    if ev:
        ev.is_active = False
        db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Public service API used by app/api/sacraments.py
# ─────────────────────────────────────────────────────────────────────────────

def _to_read(sac: Sacrament) -> SacramentRead:
    # NOTE: SacramentRead expects top-level `parishioner_id`
    return SacramentRead.model_validate(
        {
            "id": sac.id,
            "sacrament_type": _norm_type(sac.type),
            "date": sac.date,
            "fee": _to_float(getattr(sac, "fee", 0)),
            "notes": getattr(sac, "notes", None),
            "parishioner_id": sac.parishioner_id,  # ← fixed
            "details": getattr(sac, "details", {}) or {},
            "created_at": getattr(sac, "created_at", None),
        }
    )


def create_sacrament(db: Session, payload: SacramentCreate) -> SacramentRead:
    sac = Sacrament(
        type=_enum_type(payload.sacrament_type),
        date=payload.date,
        parishioner_id=payload.parishioner_id,
        fee=payload.fee,
        details=(jsonable_encoder(payload.details) if payload.details is not None else {}),
        notes=payload.notes,
    )
    db.add(sac)
    db.flush()  # get sac.id

    _sync_transaction_for_sacrament(db, sac)
    _sync_calendar_for_sacrament(db, sac)

    db.refresh(sac)
    return _to_read(sac)


def get_sacrament(db: Session, sac_id: int) -> Optional[Sacrament]:
    return db.get(Sacrament, sac_id)


def list_sacraments(db: Session, skip: int = 0, limit: int = 100) -> List[SacramentRead]:
    rows = (
        db.execute(
            select(Sacrament).order_by(Sacrament.id.desc()).offset(skip).limit(limit)
        )
        .scalars()
        .all()
    )
    return [_to_read(s) for s in rows]


def update_sacrament(db: Session, sac_id: int, patch: Dict[str, Any]) -> Optional[SacramentRead]:
    sac = db.get(Sacrament, sac_id)
    if not sac:
        return None

    if "sacrament_type" in patch and patch["sacrament_type"] is not None:
        sac.type = _enum_type(patch["sacrament_type"])
    if "date" in patch and patch["date"] is not None:
        d = patch["date"]
        sac.date = d if isinstance(d, _date) else _date.fromisoformat(str(d))
    if "parishioner_id" in patch and patch["parishioner_id"] is not None:
        sac.parishioner_id = int(patch["parishioner_id"])
    if "fee" in patch and patch["fee"] is not None:
        sac.fee = patch["fee"]
    if "notes" in patch:
        sac.notes = patch["notes"]
    if "details" in patch and patch["details"] is not None:
        sac.details = jsonable_encoder(patch["details"])

    db.flush()

    _sync_transaction_for_sacrament(db, sac)
    _sync_calendar_for_sacrament(db, sac)

    db.refresh(sac)
    return _to_read(sac)


def delete_sacrament(db: Session, sac_id: int) -> bool:
    sac = db.get(Sacrament, sac_id)
    if not sac:
        return False

    ref = f"SAC-{sac.id}"
    tx = db.execute(select(Transaction).where(Transaction.reference_no == ref)).scalars().first()
    if tx:
        db.delete(tx)

    _deactivate_calendar_for_sacrament(db, sac.id)

    db.delete(sac)
    db.commit()
    return True
