# app/models/rbac.py
import uuid
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, unique=True, index=True)
    display_name = Column(String(100), nullable=True)
    api_key_hash = Column(String(64), nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    # Association rows (owning side); explicit back_populates + overlaps to silence SA warnings.
    user_roles = relationship(
        "UserRole",
        back_populates="user",
        cascade="all, delete-orphan",
        overlaps="roles,users,role,user_roles",
    )

    # Convenience many-to-many; points through the association table.
    roles = relationship(
        "Role",
        secondary="user_roles",
        back_populates="users",
        overlaps="user_roles,role,users,roles,user",
    )


class Role(Base):
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    user_roles = relationship(
        "UserRole",
        back_populates="role",
        cascade="all, delete-orphan",
        overlaps="users,roles,user_roles,user,role",
    )

    users = relationship(
        "User",
        secondary="user_roles",
        back_populates="roles",
        overlaps="user_roles,user,role,roles,users",
    )

    permissions = relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan",
    )


class UserRole(Base):
    """
    Association object between User and Role.
    Composite PK (user_id, role_id) matches the typical schema and avoids a synthetic 'id'.
    """
    __tablename__ = "user_roles"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)

    user = relationship(
        "User",
        back_populates="user_roles",
        overlaps="roles,users",
    )
    role = relationship(
        "Role",
        back_populates="user_roles",
        overlaps="roles,users",
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission = Column(String(100), primary_key=True)

    role = relationship(
        "Role",
        back_populates="permissions",
    )
