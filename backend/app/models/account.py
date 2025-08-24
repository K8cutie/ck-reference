from __future__ import annotations
import enum
from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy.sql import func, text
from app.db import Base

class AccountType(str, enum.Enum):
    cash = "cash"
    bank = "bank"
    ewallet = "ewallet"
    other = "other"

class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, index=True)
    type = Column(SAEnum(AccountType, name="account_type", create_type=False), nullable=False)
    institution = Column(String(100), nullable=True)
    account_no = Column(String(100), nullable=True)
    currency = Column(String(3), nullable=False, server_default="PHP")
    opening_balance = Column(Numeric(14, 2), nullable=False, server_default="0")
    active = Column(Boolean, nullable=False, server_default=text("TRUE"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
