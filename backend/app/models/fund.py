from __future__ import annotations
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime
from sqlalchemy.sql import func, text
from app.db import Base

class Fund(Base):
    __tablename__ = "funds"

    id = Column(Integer, primary_key=True)
    code = Column(String(50), nullable=True, unique=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    restricted = Column(Boolean, nullable=False, server_default=text("FALSE"))
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
