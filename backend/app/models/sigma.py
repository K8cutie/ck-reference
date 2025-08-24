from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, func
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from app.db import Base

class SigmaLog(Base):
    __tablename__ = "sigma_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    process = Column(String(100), nullable=False, index=True)
    ctq = Column(String(100), nullable=True)  # critical-to-quality (optional)
    period_start = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    period_end   = Column(TIMESTAMP(timezone=True), nullable=False)
    units = Column(Integer, nullable=False)                    # units inspected
    opportunities_per_unit = Column(Integer, nullable=False)   # OPU
    defects = Column(Integer, nullable=False)                  # total defects
    notes = Column(Text, nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
