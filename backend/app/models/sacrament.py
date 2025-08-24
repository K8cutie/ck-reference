# backend/app/models/sacrament.py
"""SQLAlchemy model for Sacrament records.

Each Sacrament automatically triggers an Income-type Transaction
(via service-layer logic, not here in the model).
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

# ✅ Import Base compatibly (module vs package)
try:
    from app.db import Base  # preferred: app/db.py
except Exception:  # pragma: no cover
    from app.database import Base  # fallback: app/database.py


class SacramentType(str, enum.Enum):
    """Enumeration of supported sacraments."""
    BAPTISM = "BAPTISM"
    CONFIRMATION = "CONFIRMATION"
    MARRIAGE = "MARRIAGE"
    DEATH = "DEATH"
    FIRST_COMMUNION = "FIRST_COMMUNION"
    ANOINTING = "ANOINTING"


class Sacrament(Base):
    """Database table representing a single sacrament service."""

    __tablename__ = "sacraments"

    id: int = Column(Integer, primary_key=True, index=True)

    # e.g. Baptism, Marriage, etc.
    type: SacramentType = Column(
        Enum(SacramentType, name="sacramenttype"), nullable=False, index=True
    )

    # When the sacrament was administered
    date: datetime = Column(Date, nullable=False)

    # Link to parishioner (recipient)
    parishioner_id: int | None = Column(
        Integer,
        ForeignKey("parishioners.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Service fee collected (must not be negative)
    fee: float = Column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )

    # ➕  Structured extra info (kept from old schema)
    details: dict[str, Any] = Column(
        JSONB(astext_type=Text()),
        nullable=False,
        server_default="{}",
    )

    notes: str | None = Column(Text, nullable=True)

    created_at: datetime = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # --- Relationships --------------------------------------------------- #
    parishioner = relationship(
        "Parishioner",
        back_populates="sacraments",
        lazy="joined",
    )

    __table_args__ = (
        CheckConstraint("fee >= 0", name="ck_sacraments_fee_non_negative"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Sacrament(id={self.id}, type={self.type}, date={self.date}, "
            f"parishioner_id={self.parishioner_id}, fee={self.fee})>"
        )
