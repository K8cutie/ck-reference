from __future__ import annotations
import enum
from sqlalchemy import Column, Integer, String, Text, Date, Numeric, DateTime, ForeignKey
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db import Base

class PledgeStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"

class PledgeFrequency(str, enum.Enum):
    one_time = "one_time"
    weekly = "weekly"
    monthly = "monthly"
    quarterly = "quarterly"
    annual = "annual"

class Pledge(Base):
    __tablename__ = "pledges"

    id = Column(Integer, primary_key=True)
    parishioner_id = Column(Integer, ForeignKey("parishioners.id", ondelete="SET NULL"), nullable=True, index=True)
    fund_id = Column(Integer, ForeignKey("funds.id", ondelete="SET NULL"), nullable=True, index=True)

    pledge_date = Column(Date, nullable=False)
    amount_total = Column(Numeric(14, 2), nullable=False)

    frequency = Column(SAEnum(PledgeFrequency, name="pledge_frequency", create_type=False),
                       nullable=False, server_default="one_time")
    status = Column(SAEnum(PledgeStatus, name="pledge_status", create_type=False),
                    nullable=False, server_default="ACTIVE")

    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    fund = relationship("Fund")
    parishioner = relationship("Parishioner")
