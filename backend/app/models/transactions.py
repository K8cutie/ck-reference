from __future__ import annotations

import enum
from sqlalchemy import (
    Column, Integer, String, Date, Numeric, Enum, ForeignKey,
    DateTime, Boolean, text
)
from sqlalchemy.orm import relationship
from app.db import Base


# ---- Enums -------------------------------------------------------------------
class TransactionType(str, enum.Enum):
    income = "income"
    expense = "expense"


class PaymentMethod(str, enum.Enum):
    cash = "cash"
    gcash = "gcash"
    check = "check"
    bank = "bank"
    other = "other"


# ---- Model -------------------------------------------------------------------
class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)

    # Core
    date = Column(Date, nullable=False)
    description = Column(String, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    type = Column(Enum(TransactionType), nullable=False)

    # Links
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    category = relationship("Category", backref="transactions")

    parishioner_id = Column(Integer, ForeignKey("parishioners.id"), nullable=True)
    parishioner = relationship("Parishioner", backref="transactions")

    # NEW: accounts / funds / pledges
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    fund_id = Column(Integer, ForeignKey("funds.id", ondelete="SET NULL"), nullable=True, index=True)
    pledge_id = Column(Integer, ForeignKey("pledges.id", ondelete="SET NULL"), nullable=True, index=True)

    account = relationship("Account", backref="transactions")
    fund = relationship("Fund", backref="transactions")
    pledge = relationship("Pledge", backref="payments")

    # Payment metadata
    payment_method = Column(Enum(PaymentMethod), nullable=True)
    reference_no = Column(String, nullable=True)

    # NEW: transfer / batching / reconciliation
    transfer_ref = Column(String(100), nullable=True, index=True)
    batch_id = Column(String(100), nullable=True, index=True)
    reconciled = Column(Boolean, nullable=False, server_default=text("FALSE"), index=True)
    reconciled_at = Column(DateTime(timezone=True), nullable=True)

    # Voiding / audit trail
    voided = Column(Boolean, nullable=False, server_default=text("FALSE"))
    voided_at = Column(DateTime(timezone=True), nullable=True)
    void_reason = Column(String(255), nullable=True)
