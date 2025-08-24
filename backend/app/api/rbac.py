# app/api/rbac.py
from __future__ import annotations

import os
import secrets
import uuid
from datetime import datetime
from typing import Callable, Iterable, List, Optional, Sequence, Set

from fastapi import APIRouter, Depends, Header, HTTPException, Path, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db  # project-standard DB dependency
from app.models.rbac import User, Role, UserRole, RolePermission  # ORM models


router = APIRouter(prefix="/rbac", tags=["RBAC"])

# ---- Utilities ----------------------------------------------------------------

def _rbac_enabled() -> bool:
    """Return True if RBAC should be enforced (production), False in dev."""
    return os.getenv("RBAC_ENFORCE", "false").lower() in {"1", "true", "yes", "on"}


def _hash_api_key(api_key_plain: str) -> str:
    """Hash the plaintext API key. (sha256 hex; store only the hash)."""
    import hashlib
    pepper = os.getenv("API_KEY_PEPPER", "")
    h = hashlib.sha256()
    h.update((api_key_plain + pepper).encode("utf-8"))
    return h.hexdigest()


def _collect_user_permissions(db: Session, user_id: uuid.UUID) -> Set[str]:
    """Return the set of permission strings granted to the user via roles."""
    rp_rows = (
        db.execute(
            select(RolePermission.permission)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
        .scalars()
        .all()
    )
    return set(rp_rows)


def _perm_match(user_perm: str, required: str) -> bool:
    """Wildcard-aware permission check."""
    if user_perm == "*":
        return True
    if user_perm.endswith(":*"):
        prefix = user_perm[:-2]
        return required == prefix or required.startswith(prefix + ":")
    return user_perm == required


def _has_permission(granted: Iterable[str], required: str) -> bool:
    return any(_perm_match(p, required) for p in granted)


# ---- Auth dependencies ---------------------------------------------------------

def get_current_user(
    db: Session = Depends(get_db),
    api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> User:
    """
    Resolve the calling user. In dev (RBAC_ENFORCE=false), return a lightweight
    dev principal and skip DB lookups entirely.
    """
    if not _rbac_enabled():
        class _DevPrincipal:
            id = uuid.UUID("00000000-0000-0000-0000-000000000000")
            email = "dev@local"
            display_name = "Dev"
            api_key_hash = None
            is_active = True
        return _DevPrincipal()  # type: ignore[return-value]

    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key")

    api_key_hash = _hash_api_key(api_key)
    user = (
        db.execute(
            select(User).where(and_(User.api_key_hash == api_key_hash, User.is_active == True))  # noqa: E712
        )
        .scalars()
        .first()
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return user


def require_permission(required_permission: str) -> Callable[..., User]:
    """Dependency factory to enforce a specific permission (wildcards supported)."""
    def _inner(
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ) -> User:
        # Dev mode: skip permission checks entirely.
        if not _rbac_enabled():
            return user
        granted = _collect_user_permissions(db, user.id)
        if not _has_permission(granted, required_permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {required_permission}",
            )
        return user
    return _inner


# ---- Schemas ------------------------------------------------------------------

class RoleCreate(BaseModel):
    name: str = Field(..., max_length=50)
    description: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)


class RoleOut(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    permissions: List[str]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_with_perms(cls, role: Role, perms: Sequence[str]) -> "RoleOut":
        return cls(
            id=role.id,
            name=role.name,
            description=role.description,
            permissions=list(sorted(set(perms))),
            created_at=role.created_at,
            updated_at=role.updated_at,
        )


class RolePatch(BaseModel):
    name: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    permissions: Optional[List[str]] = None  # if provided, replace set


class UserCreate(BaseModel):
    email: str  # allow dev/test domains like .local
    display_name: Optional[str] = None
    role_ids: List[uuid.UUID] = Field(default_factory=list)
    api_key_plain: Optional[str] = Field(default=None, min_length=16)  # returned once


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: Optional[str]
    is_active: bool
    role_ids: List[uuid.UUID]
    api_key: Optional[str] = None  # only on creation


class UserPatch(BaseModel):
    display_name: Optional[str] = None
    is_active: Optional[bool] = None
    role_ids: Optional[List[uuid.UUID]] = None  # if provided, replace assignments


# ---- Role endpoints -----------------------------------------------------------

@router.post(
    "/roles",
    response_model=RoleOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("rbac:manage"))],
)
def create_role(payload: RoleCreate, db: Session = Depends(get_db)):
    role = Role(id=uuid.uuid4(), name=payload.name.strip(), description=payload.description)
    db.add(role)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Role name already exists")

    perms = []
    for p in payload.permissions:
        p = p.strip()
        if not p:
            continue
        perms.append(p)
        db.add(RolePermission(role_id=role.id, permission=p))
    db.commit()
    return RoleOut.from_orm_with_perms(role, perms)


@router.get("/roles", response_model=List[RoleOut], dependencies=[Depends(require_permission("rbac:manage"))])
def list_roles(db: Session = Depends(get_db)):
    roles = db.execute(select(Role)).scalars().all()
    out: List[RoleOut] = []
    for r in roles:
        perms = db.execute(select(RolePermission.permission).where(RolePermission.role_id == r.id)).scalars().all()
        out.append(RoleOut.from_orm_with_perms(r, perms))
    return out


@router.patch("/roles/{role_id}", response_model=RoleOut, dependencies=[Depends(require_permission("rbac:manage"))])
def patch_role(
    role_id: uuid.UUID,
    payload: RolePatch,
    db: Session = Depends(get_db),
):
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if payload.name is not None:
        role.name = payload.name.strip()
    if payload.description is not None:
        role.description = payload.description

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Role name already exists")

    perms = db.execute(select(RolePermission.permission).where(RolePermission.role_id == role_id)).scalars().all()

    if payload.permissions is not None:
        db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
        db.flush()
        perms = []
        for p in payload.permissions:
            p = p.strip()
            if not p:
                continue
            perms.append(p)
            db.add(RolePermission(role_id=role_id, permission=p))

    db.commit()
    return RoleOut.from_orm_with_perms(role, perms)


@router.delete(
    "/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("rbac:manage"))],
)
def delete_role(role_id: uuid.UUID, db: Session = Depends(get_db)):
    role = db.get(Role, role_id)
    if not role:
        return
    db.delete(role)
    db.commit()
    return


# ---- User endpoints -----------------------------------------------------------

@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("rbac:manage"))])
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    api_key_plain = payload.api_key_plain or secrets.token_urlsafe(32)
    api_key_hash = _hash_api_key(api_key_plain)

    user = User(
        id=uuid.uuid4(),
        email=str(payload.email).lower(),
        display_name=payload.display_name,
        api_key_hash=api_key_hash,
        is_active=True,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="User email already exists")

    for rid in payload.role_ids:
        db.add(UserRole(user_id=user.id, role_id=rid))
    db.commit()

    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        role_ids=payload.role_ids,
        api_key=api_key_plain,
    )


@router.get("/users", response_model=List[UserOut], dependencies=[Depends(require_permission("rbac:manage"))])
def list_users(db: Session = Depends(get_db)):
    users = db.execute(select(User)).scalars().all()
    out: List[UserOut] = []
    for u in users:
        role_ids = db.execute(select(UserRole.role_id).where(UserRole.user_id == u.id)).scalars().all()
        out.append(
            UserOut(
                id=u.id,
                email=u.email,
                display_name=u.display_name,
                is_active=u.is_active,
                role_ids=role_ids,
            )
        )
    return out


@router.patch("/users/{user_id}", response_model=UserOut, dependencies=[Depends(require_permission("rbac:manage"))])
def patch_user(user_id: uuid.UUID, payload: UserPatch, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.is_active is not None:
        user.is_active = payload.is_active

    if payload.role_ids is not None:
        db.execute(delete(UserRole).where(UserRole.user_id == user_id))
        for rid in payload.role_ids:
            db.add(UserRole(user_id=user_id, role_id=rid))

    db.commit()

    role_ids = db.execute(select(UserRole.role_id).where(UserRole.user_id == user_id)).scalars().all()
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        role_ids=role_ids,
    )


# ---- Helper / demo ------------------------------------------------------------

class WhoAmI(BaseModel):
    id: uuid.UUID
    email: str
    display_name: Optional[str]
    permissions: List[str]


@router.get("/whoami", response_model=WhoAmI, dependencies=[Depends(require_permission("rbac:manage"))])
def whoami(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _rbac_enabled():
        return WhoAmI(
            id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            email="dev@local",
            display_name="Dev",
            permissions=["*", "rbac:*", "rbac:manage"],
        )
    perms = sorted(_collect_user_permissions(db, user.id))
    return WhoAmI(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        permissions=perms,
    )


# Expose the permission guard for other routers to import
permission_required = require_permission
