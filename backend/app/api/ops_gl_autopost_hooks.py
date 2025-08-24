# app/api/ops_gl_autopost_hooks.py
# Auto-post new ops Transactions into Books (GL) using SQLAlchemy session hooks.

from __future__ import annotations
from typing import Set
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.transactions import Transaction
from app.services.ops_gl_sync import ensure_tx_synced_to_gl

_HOOKS_REGISTERED = False

def register_ops_gl_autopost_hooks() -> None:
    global _HOOKS_REGISTERED
    if _HOOKS_REGISTERED:
        return
    _HOOKS_REGISTERED = True

    @event.listens_for(Session, "after_flush")
    def _capture_new_transactions(session: Session, flush_ctx) -> None:
        # Remember newly created Transaction IDs for this unit of work
        ids: Set[int] = session.info.setdefault("_new_tx_ids", set())
        for obj in session.new:
            if isinstance(obj, Transaction) and getattr(obj, "id", None) is not None:
                if getattr(obj, "voided", False):
                    continue
                ids.add(int(obj.id))

    @event.listens_for(Session, "after_commit")
    def _sync_to_books(session: Session) -> None:
        ids: Set[int] = session.info.pop("_new_tx_ids", set())
        if not ids:
            return
        # Use a fresh DB session to create/post JEs
        with SessionLocal() as db:
            for tx_id in ids:
                tx = db.get(Transaction, tx_id)
                if not tx:
                    continue
                try:
                    ensure_tx_synced_to_gl(db, tx)
                    db.commit()
                except Exception:
                    db.rollback()
                    # Optional: add proper logging here

# Auto-register on import (guarded)
register_ops_gl_autopost_hooks()
