# app/models/parishioners.py
from __future__ import annotations

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

# Prefer app/db.py; fall back to app/database.py if needed
try:
    from app.db import Base  # type: ignore
except Exception:  # pragma: no cover
    from app.database import Base  # type: ignore


class Parishioner(Base):
    __tablename__ = "parishioners"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    middle_name = Column(String(100), nullable=True)   # NEW
    last_name = Column(String, nullable=False)
    suffix = Column(String(20), nullable=True)         # NEW
    contact_number = Column(String, nullable=True)

    # Back-populated by Sacrament.parishioner
    sacraments = relationship(
        "Sacrament",
        back_populates="parishioner",
        lazy="selectin",
    )
