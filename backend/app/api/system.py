# app/api/system.py
from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from sqlalchemy import create_engine, text

router = APIRouter(tags=["ops"])


def _db_driver_from_url(url: str | None) -> str | None:
    if not url or "://" not in url:
        return None
    scheme = url.split("://", 1)[0]  # e.g., "postgresql+psycopg2"
    if "+" in scheme:
        return scheme.split("+", 1)[1]  # "psycopg2"
    return scheme  # fallback


@router.get("/health")
def health():
    """Liveness check with a lightweight DB probe and local time."""
    tz = os.getenv("TZ", "Asia/Manila")
    now_local = datetime.now(ZoneInfo(tz)).isoformat()

    url = os.getenv("DATABASE_URL")
    db = {"status": "skip", "driver": _db_driver_from_url(url)}

    if url:
        try:
            engine = create_engine(url, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db["status"] = "ok"
        except Exception as e:
            db["status"] = f"error: {type(e).__name__}"

    return {
        "status": "ok",
        "time": {"tz": tz, "now": now_local},
        "db": db,
    }


@router.get("/version")
def version():
    """Minimal runtime info; confirms DB driver for the UI."""
    url = os.getenv("DATABASE_URL")
    tz = os.getenv("TZ", "Asia/Manila")

    return {
        "app": "ClearKeep Backend",
        "db_driver": _db_driver_from_url(url),
        "tz": tz,
    }
