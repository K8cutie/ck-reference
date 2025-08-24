# backend/app/api/sacraments.py
from __future__ import annotations

from typing import List, Dict, Any

import logging
from fastapi import APIRouter, Depends, HTTPException, Response, Body
from sqlalchemy.orm import Session

# Prefer app/db.py; fall back to app/database.py
try:
    from app.db import get_db  # type: ignore
except Exception:  # pragma: no cover
    from app.database import get_db  # type: ignore

from app.schemas.sacrament import SacramentCreate, SacramentRead
from app.services import sacraments as svc

router = APIRouter(prefix="/sacraments", tags=["Sacraments"])
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# OpenAPI "examples" for request body
# ─────────────────────────────────────────────────────────────────────────────
CREATE_EXAMPLES: Dict[str, Dict[str, Any]] = {
    "confirmation": {
        "summary": "Confirmation",
        "description": "Typical confirmation record.",
        "value": {
            "parishioner_id": 1,
            "date": "2025-08-08",
            "fee": 450,
            "notes": "Evening batch",
            "sacrament_type": "confirmation",
            "details": {
                "confirmand": "Juan Dela Cruz",
                "sponsor_names": ["Maria Santos", "Jose Reyes"],
                "preparation_class_batch": "2025-Q3",
            },
        },
    },
    "baptism": {
        "summary": "Baptism",
        "description": "Baptism with required details. Time/location are optional.",
        "value": {
            "parishioner_id": 1,
            "date": "2025-08-22",
            "fee": 500,
            "notes": "10 AM batch",
            "sacrament_type": "baptism",
            "details": {
                "mother": "Jane Doe",
                "father": "John Doe",
                "child_name": "Baby Doe",
                "god_parents": ["Sponsor A", "Sponsor B"],
                "time": "10:00",
                "location": "Main Church"
            },
        },
    },
}

OPENAPI_REQUEST_EXAMPLES = {
    "requestBody": {
        "content": {
            "application/json": {
                "examples": CREATE_EXAMPLES
            }
        }
    }
}


@router.post(
    "/",
    response_model=SacramentRead,
    status_code=201,
    openapi_extra=OPENAPI_REQUEST_EXAMPLES,  # show examples in Swagger
)
def create_sacrament(
    payload: SacramentCreate,
    db: Session = Depends(get_db),
) -> SacramentRead:
    # Minimal debug to verify what the server actually received
    try:
        logger.info(
            "create_sacrament received: type=%s parishioner_id=%s date=%s",
            getattr(payload, "sacrament_type", None),
            getattr(payload, "parishioner_id", None),
            getattr(payload, "date", None),
        )
    except Exception:
        # Never block the request if logging fails
        logger.debug("create_sacrament: failed to log payload snapshot", exc_info=True)

    return svc.create_sacrament(db, payload)


@router.get("/{sacrament_id}", response_model=SacramentRead)
def get_sacrament(sacrament_id: int, db: Session = Depends(get_db)) -> SacramentRead:
    sac = svc.get_sacrament(db, sacrament_id)
    if not sac:
        raise HTTPException(status_code=404, detail="Sacrament not found")
    # convert ORM -> read DTO using service helper
    return svc._to_read(sac)  # type: ignore[attr-defined]


@router.get("/", response_model=List[SacramentRead])
def list_sacraments(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[SacramentRead]:
    return svc.list_sacraments(db, skip=skip, limit=limit)


@router.patch("/{sacrament_id}", response_model=SacramentRead)
def update_sacrament(
    sacrament_id: int,
    payload: dict = Body(...),  # accept partial dict to avoid Pydantic union quirks
    db: Session = Depends(get_db),
) -> SacramentRead:
    # Log only the fields being patched (helps trace id mismatches)
    try:
        safe_keys = list(payload.keys()) if isinstance(payload, dict) else "N/A"
        logger.info("update_sacrament id=%s fields=%s", sacrament_id, safe_keys)
    except Exception:
        logger.debug("update_sacrament: failed to log patch keys", exc_info=True)

    sac = svc.update_sacrament(db, sacrament_id, payload)
    if not sac:
        raise HTTPException(status_code=404, detail="Sacrament not found")
    return sac


# 204 must have no body — use Response explicitly
@router.delete("/{sacrament_id}", status_code=204, response_class=Response)
def delete_sacrament(sacrament_id: int, db: Session = Depends(get_db)) -> Response:
    ok = svc.delete_sacrament(db, sacrament_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Sacrament not found")
    return Response(status_code=204)
