# app/models/gl_accounting.py
from __future__ import annotations

from datetime import datetime, date
from typing import List, Optional

from sqlalchemy import (
    String, Boolean, Date, DateTime, Numeric, Text,
    ForeignKey, Index, Integer, BigInteger, text
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import ENUM as PGEnum

# Your project Base lives here:
from app.db import Base


# Reuse existing PostgreSQL ENUM types (created by Alembic migration)
AccountTypeEnum = PGEnum(
    "asset", "liability", "equity", "income", "expense",
    name="gl_account_type",
    create_type=False,
)
NormalSideEnum = PGEnum(
    "debit", "credit",
    name="gl_normal_side",
    create_type=False,
)


class GLAccount(Base):
    __tablename__ = "gl_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    type: Mapped[str] = mapped_column(AccountTypeEnum, nullable=False)
    normal_side: Mapped[str] = mapped_column(NormalSideEnum, nullable=False)
    is_cash: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    # relationships
    lines: Mapped[List["JournalLine"]] = relationship(
        "JournalLine",
        back_populates="account",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_gl_accounts_code", "code"),
        Index("ix_gl_accounts_type", "type"),
        Index("ix_gl_accounts_is_cash", "is_cash"),
    )

    def __repr__(self) -> str:
        return f"<GLAccount {self.code} {self.name} ({self.type})>"


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_no: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("nextval('je_entry_no_seq')"))
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    memo: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, server_default="PHP")

    # Linkage to operational source
    reference_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_module: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Posting/locking for audit trail
    created_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    posted_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    # relationships
    lines: Mapped[List["JournalLine"]] = relationship(
        "JournalLine",
        back_populates="entry",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="JournalLine.line_no.asc()",
    )

    __table_args__ = (
        Index("ix_journal_entries_date", "entry_date"),
        Index("ix_journal_entries_refno", "reference_no"),
        Index("ix_journal_entries_source", "source_module", "source_id"),
    )

    # convenience properties (service layer will enforce balance)
    @property
    def total_debits(self) -> float:
        return float(sum((line.debit or 0) for line in self.lines))

    @property
    def total_credits(self) -> float:
        return float(sum((line.credit or 0) for line in self.lines))

    @property
    def is_balanced(self) -> bool:
        return round(self.total_debits - self.total_credits, 2) == 0.0

    def __repr__(self) -> str:
        return f"<JE #{self.entry_no} {self.entry_date} ref={self.reference_no}>"


class JournalLine(Base):
    __tablename__ = "journal_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("gl_accounts.id", ondelete="RESTRICT"), nullable=False)

    line_no: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    description: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    debit: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    credit: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    # relationships
    entry: Mapped["JournalEntry"] = relationship("JournalEntry", back_populates="lines")
    account: Mapped["GLAccount"] = relationship("GLAccount", back_populates="lines")

    __table_args__ = (
        Index("ix_journal_lines_entry", "entry_id"),
        Index("ix_journal_lines_account", "account_id"),
    )

    def __repr__(self) -> str:
        side = "DR" if (self.debit or 0) > 0 else "CR"
        amt = self.debit or self.credit or 0
        return f"<JL {side} {amt} L{self.line_no} A={self.account_id}>"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)   # e.g., 'journal_entry'
    entity_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)        # e.g., 'create','post','void','reprint'
    user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)    # JSON text if needed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Audit {self.entity_type}:{self.entity_id} {self.action}>"
