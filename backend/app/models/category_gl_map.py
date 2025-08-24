# app/models/category_gl_map.py
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Index,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship
from app.db import Base


class CategoryGLMap(Base):
    __tablename__ = "category_gl_map"
    # Allow legacy-style annotations / relationships without Mapped[]
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True)

    # Each category may have at most one mapping row
    category_id = Column(
        Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # Optional defaults for JE lines produced by this category:
    # INCOME:  Dr (debit_account_id, usually cash/bank) / Cr (credit_account_id, income GL)
    # EXPENSE: Dr (debit_account_id, expense GL)        / Cr (credit_account_id, cash/bank)
    debit_account_id = Column(
        Integer, ForeignKey("gl_accounts.id", ondelete="SET NULL"), nullable=True
    )
    credit_account_id = Column(
        Integer, ForeignKey("gl_accounts.id", ondelete="SET NULL"), nullable=True
    )

    created_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    # Relationships (string targets avoid import cycles)
    category = relationship("Category", lazy="joined", uselist=False)
    debit_account = relationship("GLAccount", foreign_keys=[debit_account_id], lazy="joined")
    credit_account = relationship("GLAccount", foreign_keys=[credit_account_id], lazy="joined")

    __table_args__ = (
        UniqueConstraint("category_id", name="uq_category_gl_map_category_id"),
        Index("ix_category_gl_map_category_id", "category_id"),
        Index("ix_category_gl_map_debit_account_id", "debit_account_id"),
        Index("ix_category_gl_map_credit_account_id", "credit_account_id"),
    )
