from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, PositiveInt
from sqlalchemy import select, and_, or_, func, case
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.transactions import Transaction, TransactionType
from app.models.account import Account
from app.models.fund import Fund
from app.models.compliance import (
    ComplianceConfig as ComplianceConfigDB,
    ComplianceConfigAudit,
)

router = APIRouter(prefix="/compliance", tags=["Compliance"])

# -------------------- helpers (env + optional file seed) --------------------

def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}

def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default

def _file_config_path() -> Path:
    # .../app/_data/compliance_config.json
    base = Path(__file__).resolve().parents[1]
    data_dir = base / "_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "compliance_config.json"

def _load_file_config_if_any() -> Optional[dict]:
    p = _file_config_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _to_float(x) -> float:
    if x is None:
        return 0.0
    if isinstance(x, Decimal):
        return float(x)
    return float(x)

def _like(q: str) -> str:
    return f"%{q}%"


# ------------------------------- Schemas ------------------------------------

class ConfigOut(BaseModel):
    enforce_voids: bool = True
    allow_hard_delete: bool = False
    retention_days: PositiveInt = 3650
    updated_at: Optional[datetime] = None

class ConfigPatch(BaseModel):
    enforce_voids: Optional[bool] = None
    allow_hard_delete: Optional[bool] = None
    retention_days: Optional[PositiveInt] = None


# --------------------- Single-row loader / seeding --------------------------

def _ensure_config_row(db: Session) -> ComplianceConfigDB:
    cfg = db.get(ComplianceConfigDB, 1)
    if cfg:
        return cfg

    # Seed from file if present, else from ENV defaults
    file_data = _load_file_config_if_any()
    if file_data:
        enforce = bool(file_data.get("enforce_voids", True))
        allow = bool(file_data.get("allow_hard_delete", False))
        retention = int(file_data.get("retention_days", 3650))
        source = "seed:file"
    else:
        enforce = _env_bool("COMPLIANCE_ENFORCE_VOIDS", True)
        allow = _env_bool("COMPLIANCE_ALLOW_HARD_DELETE", False)
        retention = _env_int("COMPLIANCE_RETENTION_DAYS", 3650)
        source = "seed:env"

    cfg = ComplianceConfigDB(
        id=1,
        enforce_voids=enforce,
        allow_hard_delete=allow,
        retention_days=retention,
    )
    db.add(cfg)
    db.flush()

    db.add(ComplianceConfigAudit(
        enforce_voids=cfg.enforce_voids,
        allow_hard_delete=cfg.allow_hard_delete,
        retention_days=cfg.retention_days,
        changed_by=None,
        source=source,
    ))

    # If we seeded from file, rename it so we don’t import again
    try:
        if file_data:
            p = _file_config_path()
            p.rename(p.with_suffix(".json.bak"))
    except Exception:
        pass

    db.commit()
    db.refresh(cfg)
    return cfg


# ----------------------------- Config endpoints -----------------------------

@router.get("/config", response_model=ConfigOut)
def get_config(db: Session = Depends(get_db)) -> ConfigOut:
    cfg = _ensure_config_row(db)
    return ConfigOut(
        enforce_voids=cfg.enforce_voids,
        allow_hard_delete=cfg.allow_hard_delete,
        retention_days=cfg.retention_days,
        updated_at=cfg.updated_at,
    )


@router.patch("/config", response_model=ConfigOut)
def patch_config(payload: ConfigPatch, db: Session = Depends(get_db)) -> ConfigOut:
    cfg = _ensure_config_row(db)
    changes = payload.model_dump(exclude_unset=True)
    if "enforce_voids" in changes and changes["enforce_voids"] is not None:
        cfg.enforce_voids = changes["enforce_voids"]
    if "allow_hard_delete" in changes and changes["allow_hard_delete"] is not None:
        cfg.allow_hard_delete = changes["allow_hard_delete"]
    if "retention_days" in changes and changes["retention_days"] is not None:
        cfg.retention_days = int(changes["retention_days"])

    db.add(cfg)
    db.flush()

    db.add(ComplianceConfigAudit(
        enforce_voids=cfg.enforce_voids,
        allow_hard_delete=cfg.allow_hard_delete,
        retention_days=cfg.retention_days,
        changed_by=None,  # hook to auth later
        source="api",
    ))
    db.commit()
    db.refresh(cfg)

    return ConfigOut(
        enforce_voids=cfg.enforce_voids,
        allow_hard_delete=cfg.allow_hard_delete,
        retention_days=cfg.retention_days,
        updated_at=cfg.updated_at,
    )


# --------------------------- Voids listing/export ---------------------------

class VoidFilter(BaseModel):
    # Filter by transaction DATE (original txn date). Use by=voided_at to filter by void time.
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    type: Optional[TransactionType] = None
    account_id: Optional[int] = None
    fund_id: Optional[int] = None
    q: Optional[str] = None           # search description / reference_no / transfer_ref
    by: str = Field("tx_date", pattern="^(tx_date|voided_at)$")
    skip: int = 0
    limit: int = 200

def _voids_base_query(by: str, vf: VoidFilter):
    conds = [Transaction.voided.is_(True)]
    if vf.date_from is not None:
        if by == "voided_at":
            conds.append(func.date(Transaction.voided_at) >= vf.date_from)
        else:
            conds.append(Transaction.date >= vf.date_from)
    if vf.date_to is not None:
        if by == "voided_at":
            conds.append(func.date(Transaction.voided_at) <= vf.date_to)
        else:
            conds.append(Transaction.date <= vf.date_to)

    if vf.type is not None:
        conds.append(Transaction.type == vf.type)
    if vf.account_id is not None:
        conds.append(Transaction.account_id == vf.account_id)
    if vf.fund_id is not None:
        conds.append(Transaction.fund_id == vf.fund_id)
    if vf.q:
        like = _like(vf.q)
        conds.append(
            or_(
                Transaction.description.ilike(like),
                Transaction.reference_no.ilike(like),
                Transaction.transfer_ref.ilike(like),
            )
        )
    return and_(*conds)

@router.get("/voids")
def list_voids(
    db: Session = Depends(get_db),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    type: Optional[TransactionType] = Query(None, description="'income' or 'expense'"),
    account_id: Optional[int] = None,
    fund_id: Optional[int] = None,
    q: Optional[str] = Query(None, description="Search description / reference / transfer"),
    by: str = Query("tx_date", pattern="^(tx_date|voided_at)$"),
    skip: int = 0,
    limit: int = Query(200, le=500),
):
    vf = VoidFilter(
        date_from=date_from,
        date_to=date_to,
        type=type,
        account_id=account_id,
        fund_id=fund_id,
        q=q,
        by=by,
        skip=skip,
        limit=limit,
    )
    where_clause = _voids_base_query(by, vf)

    stmt = (
        select(
            Transaction.id,
            Transaction.date,
            Transaction.description,
            Transaction.amount,
            Transaction.type,
            Transaction.account_id,
            Account.name.label("account_name"),
            Transaction.fund_id,
            Fund.name.label("fund_name"),
            Transaction.reference_no,
            Transaction.transfer_ref,
            Transaction.voided_at,
            Transaction.void_reason,
        )
        .outerjoin(Account, Account.id == Transaction.account_id)
        .outerjoin(Fund, Fund.id == Transaction.fund_id)
        .where(where_clause)
        .order_by(
            (func.coalesce(Transaction.voided_at, Transaction.date)).desc(),
            Transaction.id.desc(),
        )
        .offset(vf.skip)
        .limit(vf.limit)
    )

    rows = db.execute(stmt).all()
    items = [
        {
            "id": rid,
            "date": str(dt),
            "description": desc,
            "amount": _to_float(amt),
            "type": (t.value if hasattr(t, "value") else str(t)),
            "account_id": aid,
            "account_name": aname,
            "fund_id": fid,
            "fund_name": fname,
            "reference_no": ref,
            "transfer_ref": txref,
            "voided_at": (va.isoformat() if va else None),
            "void_reason": vreason,
        }
        for (
            rid, dt, desc, amt, t, aid, aname, fid, fname, ref, txref, va, vreason
        ) in rows
    ]
    return {"filters": vf.model_dump(), "items": items, "count": len(items)}

@router.get("/voids/export.csv")
def export_voids_csv(
    db: Session = Depends(get_db),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    type: Optional[TransactionType] = Query(None, description="'income' or 'expense'"),
    account_id: Optional[int] = None,
    fund_id: Optional[int] = None,
    q: Optional[str] = Query(None),
    by: str = Query("tx_date", pattern="^(tx_date|voided_at)$"),
):
    vf = VoidFilter(
        date_from=date_from,
        date_to=date_to,
        type=type,
        account_id=account_id,
        fund_id=fund_id,
        q=q,
        by=by,
        skip=0,
        limit=100000,  # effectively unlimited for CSV
    )
    where_clause = _voids_base_query(by, vf)

    stmt = (
        select(
            Transaction.id,
            Transaction.date,
            Transaction.type,
            Transaction.amount,
            Transaction.description,
            Account.name.label("account_name"),
            Fund.name.label("fund_name"),
            Transaction.reference_no,
            Transaction.transfer_ref,
            Transaction.voided_at,
            Transaction.void_reason,
        )
        .outerjoin(Account, Account.id == Transaction.account_id)
        .outerjoin(Fund, Fund.id == Transaction.fund_id)
        .where(where_clause)
        .order_by(
            (func.coalesce(Transaction.voided_at, Transaction.date)).desc(),
            Transaction.id.desc(),
        )
    )

    def row_iter():
        cols = [
            "id","date","type","amount","description","account_name","fund_name",
            "reference_no","transfer_ref","voided_at","void_reason",
        ]
        yield ",".join(cols) + "\n"

        def esc(v):
            if v is None:
                return ""
            s = str(v)
            if any(c in s for c in [",", '"', "\n", "\r"]):
                s = '"' + s.replace('"', '""') + '"'
            return s

        for r in db.execute(stmt):
            row = [
                r.id,
                r.date,
                (r.type.value if hasattr(r.type, "value") else r.type),
                _to_float(r.amount),
                r.description or "",
                r.account_name or "",
                r.fund_name or "",
                r.reference_no or "",
                r.transfer_ref or "",
                r.voided_at.isoformat() if r.voided_at else "",
                r.void_reason or "",
            ]
            yield ",".join(esc(x) for x in row) + "\n"

    return StreamingResponse(
        row_iter(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="voids_audit.csv"'},
    )


# ------------------------ Config audit list + export ------------------------

class AuditFilter(BaseModel):
    changed_from: Optional[date] = None
    changed_to: Optional[date] = None
    changed_by: Optional[str] = None
    source: Optional[str] = None
    skip: int = 0
    limit: int = 200

def _audit_base_query(af: AuditFilter):
    conds = []
    if af.changed_from is not None:
        conds.append(func.date(ComplianceConfigAudit.changed_at) >= af.changed_from)
    if af.changed_to is not None:
        conds.append(func.date(ComplianceConfigAudit.changed_at) <= af.changed_to)
    if af.changed_by:
        conds.append(ComplianceConfigAudit.changed_by.ilike(_like(af.changed_by)))
    if af.source:
        conds.append(ComplianceConfigAudit.source.ilike(_like(af.source)))
    return and_(*conds) if conds else True

@router.get("/audit")
def list_config_audit(
    db: Session = Depends(get_db),
    changed_from: Optional[date] = None,
    changed_to: Optional[date] = None,
    changed_by: Optional[str] = None,
    source: Optional[str] = None,
    skip: int = 0,
    limit: int = Query(200, le=1000),
):
    af = AuditFilter(
        changed_from=changed_from,
        changed_to=changed_to,
        changed_by=changed_by,
        source=source,
        skip=skip,
        limit=limit,
    )
    where_clause = _audit_base_query(af)

    stmt = (
        select(
            ComplianceConfigAudit.id,
            ComplianceConfigAudit.changed_at,
            ComplianceConfigAudit.enforce_voids,
            ComplianceConfigAudit.allow_hard_delete,
            ComplianceConfigAudit.retention_days,
            ComplianceConfigAudit.changed_by,
            ComplianceConfigAudit.source,
        )
        .where(where_clause)
        .order_by(ComplianceConfigAudit.changed_at.desc(), ComplianceConfigAudit.id.desc())
        .offset(af.skip)
        .limit(af.limit)
    )
    rows = db.execute(stmt).all()
    items = [
        {
            "id": rid,
            "changed_at": ca.isoformat() if ca else None,
            "enforce_voids": ev,
            "allow_hard_delete": ahd,
            "retention_days": rd,
            "changed_by": cb,
            "source": src,
        }
        for (rid, ca, ev, ahd, rd, cb, src) in rows
    ]
    return {"filters": af.model_dump(), "items": items, "count": len(items)}

@router.get("/audit/export.csv")
def export_config_audit_csv(
    db: Session = Depends(get_db),
    changed_from: Optional[date] = None,
    changed_to: Optional[date] = None,
    changed_by: Optional[str] = None,
    source: Optional[str] = None,
):
    af = AuditFilter(
        changed_from=changed_from,
        changed_to=changed_to,
        changed_by=changed_by,
        source=source,
        skip=0,
        limit=100000,
    )
    where_clause = _audit_base_query(af)

    stmt = (
        select(
            ComplianceConfigAudit.id,
            ComplianceConfigAudit.changed_at,
            ComplianceConfigAudit.enforce_voids,
            ComplianceConfigAudit.allow_hard_delete,
            ComplianceConfigAudit.retention_days,
            ComplianceConfigAudit.changed_by,
            ComplianceConfigAudit.source,
        )
        .where(where_clause)
        .order_by(ComplianceConfigAudit.changed_at.desc(), ComplianceConfigAudit.id.desc())
    )

    def row_iter():
        cols = [
            "id","changed_at","enforce_voids","allow_hard_delete",
            "retention_days","changed_by","source",
        ]
        yield ",".join(cols) + "\n"

        def esc(v):
            if v is None:
                return ""
            s = str(v)
            if any(c in s for c in [",", '"', "\n", "\r"]):
                s = '"' + s.replace('"', '""') + '"'
            return s

        for r in db.execute(stmt):
            row = [
                r.id,
                r.changed_at.isoformat() if r.changed_at else "",
                "true" if r.enforce_voids else "false",
                "true" if r.allow_hard_delete else "false",
                r.retention_days,
                r.changed_by or "",
                r.source or "",
            ]
            yield ",".join(esc(x) for x in row) + "\n"

    return StreamingResponse(
        row_iter(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="compliance_audit.csv"'},
    )
