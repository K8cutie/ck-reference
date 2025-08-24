# app/schemas/rbac.py
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

# Pydantic v1/v2 compatibility: enable ORM mode
class ORMBase(BaseModel):
    class Config:
        orm_mode = True


# ---------- Roles & Permissions ----------

class RolePermissionRead(ORMBase):
    permission: str = Field(..., examples=["calendar:read"])


class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    description: Optional[str] = None
    permissions: Optional[List[str]] = None


class RoleRead(ORMBase):
    id: UUID
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    permissions: List[str] = []


# ---------- Users ----------

class UserCreate(BaseModel):
    email: str
    display_name: Optional[str] = None
    # for a later step we’ll hash this into api_key_hash
    api_key_plain: Optional[str] = Field(default=None, min_length=12)
    roles: List[str] = Field(default_factory=list, description="Role names to assign")


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    is_active: Optional[bool] = None
    roles: Optional[List[str]] = None  # role names


class UserRead(ORMBase):
    id: UUID
    email: str
    display_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    roles: List[RoleRead] = []
