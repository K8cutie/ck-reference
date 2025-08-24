from __future__ import annotations

from sqlalchemy import Column, Integer, Boolean, DateTime, String, text
from sqlalchemy.sql import func

from app.db import Base


class ComplianceConfig(Base):
    __tablename__ = "compliance_config"

    id = Column(Integer, primary_key=True)  # always 1
    enforce_voids = Column(Boolean, nullable=False, server_default=text("TRUE"))
    allow_hard_delete = Column(Boolean, nullable=False, server_default=text("FALSE"))
    retention_days = Column(Integer, nullable=False, server_default=text("3650"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=func.now(),
    )


class ComplianceConfigAudit(Base):
    __tablename__ = "compliance_config_audit"

    id = Column(Integer, primary_key=True)
    changed_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    enforce_voids = Column(Boolean, nullable=False)
    allow_hard_delete = Column(Boolean, nullable=False)
    retention_days = Column(Integer, nullable=False)
    changed_by = Column(String(100), nullable=True)  # fill once auth is in place
    source = Column(String(50), nullable=True)       # e.g., "seed:env", "seed:file", "api"
