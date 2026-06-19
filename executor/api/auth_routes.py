"""Authentication & user-management routes."""
import logging
import re
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from executor.api.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    is_token_revoked,
    require_admin,
    revoke_token,
    verify_password,
)
from executor.configs.settings import settings
from executor.persistence.database import get_db_session
from executor.persistence.models import User, UserRole

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_VALID_ROLES = {r.value for r in UserRole}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None
    role: Optional[str] = None  # only honoured for the first user / by admins

    @field_validator("email")
    @classmethod
    def _email_ok(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("Invalid email address")
        return v

    @field_validator("password")
    @classmethod
    def _pw_ok(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime

    @classmethod
    def from_model(cls, u: User) -> "UserOut":
        return cls(id=str(u.id), email=u.email, full_name=u.full_name,
                   role=u.role, is_active=u.is_active, created_at=u.created_at)


class TokenResponse(BaseModel):
    success: bool = True
    message: str = "Authentication successful"
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

async def _get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    res = await db.execute(select(User).where(User.email == email))
    return res.scalar_one_or_none()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db_session)):
    if await _get_user_by_email(db, req.email):
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    # First-ever user becomes admin; otherwise default to USER. A requested role
    # is only honoured for the bootstrap (first) user.
    count = (await db.execute(select(User))).scalars().first()
    is_first = count is None
    role = UserRole.USER.value
    if is_first:
        role = (req.role if req.role in _VALID_ROLES else UserRole.ADMIN.value)

    user = User(
        email=req.email,
        full_name=req.full_name,
        hashed_password=hash_password(req.password),
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info(f"Registered new user {user.email} (role={user.role})")

    return TokenResponse(
        access_token=create_access_token(user),
        refresh_token=create_refresh_token(user),
        user=UserOut.from_model(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db_session)):
    user = await _get_user_by_email(db, req.email.strip().lower())
    if not user or not verify_password(req.password, user.hashed_password):
        # Same message for both cases to avoid user enumeration.
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    logger.info(f"User logged in: {user.email}")
    return TokenResponse(
        access_token=create_access_token(user),
        refresh_token=create_refresh_token(user),
        user=UserOut.from_model(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest, db: AsyncSession = Depends(get_db_session)):
    payload = decode_token(req.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")
    if await is_token_revoked(db, payload.get("jti")):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")

    import uuid as _uuid
    user = await db.get(User, _uuid.UUID(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # Rotate: revoke the presented refresh token, issue a fresh pair.
    await revoke_token(db, payload)
    return TokenResponse(
        message="Token refreshed",
        access_token=create_access_token(user),
        refresh_token=create_refresh_token(user),
        user=UserOut.from_model(user),
    )


@router.post("/logout")
async def logout(req: RefreshRequest, db: AsyncSession = Depends(get_db_session)):
    """Invalidate a refresh token so it can no longer be used."""
    try:
        payload = decode_token(req.refresh_token)
        await revoke_token(db, payload)
    except HTTPException:
        pass  # already invalid/expired — treat logout as success
    return {"success": True, "message": "Logged out"}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return UserOut.from_model(user)


@router.get("/users", response_model=List[UserOut])
async def list_users(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Admin-only: list all users (demonstrates RBAC)."""
    res = await db.execute(select(User).order_by(User.created_at.desc()))
    return [UserOut.from_model(u) for u in res.scalars().all()]
