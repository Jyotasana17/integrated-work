"""Authentication & RBAC core utilities.

- Password hashing via PBKDF2-HMAC-SHA256 (stdlib, no extra deps).
- JWT access/refresh tokens via PyJWT.
- FastAPI dependencies for extracting the current user and enforcing roles.
"""
import hashlib
import hmac
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from executor.configs.settings import settings
from executor.persistence.database import get_db_session
from executor.persistence.models import RevokedToken, User, UserRole

logger = logging.getLogger(__name__)

# auto_error=False so we can return our own 401 (and support AUTH_REQUIRED=False).
_bearer = HTTPBearer(auto_error=False)

_PBKDF2_ROUNDS = 240_000


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------

def _create_token(sub: str, role: str, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "role": role,
        "type": token_type,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user: User) -> str:
    return _create_token(str(user.id), user.role, "access",
                         timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(user: User) -> str:
    return _create_token(str(user.id), user.role, "refresh",
                         timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")


# ---------------------------------------------------------------------------
# Token revocation (logout / refresh rotation)
# ---------------------------------------------------------------------------

async def is_token_revoked(db: AsyncSession, jti: str) -> bool:
    if not jti:
        return False
    return (await db.get(RevokedToken, jti)) is not None


async def revoke_token(db: AsyncSession, payload: dict) -> None:
    jti = payload.get("jti")
    if not jti:
        return
    if await db.get(RevokedToken, jti):
        return
    exp = payload.get("exp")
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc) if exp else datetime.now(timezone.utc)
    db.add(RevokedToken(jti=jti, expires_at=expires_at))
    await db.commit()


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

async def _user_from_token(token: str, db: AsyncSession, expected_type: str = "access") -> User:
    payload = decode_token(token)
    if payload.get("type") != expected_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong token type")
    if await is_token_revoked(db, payload.get("jti")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")
    sub = payload.get("sub")
    user = await db.get(User, uuid.UUID(sub)) if sub else None
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """Require a valid access token; raises 401 otherwise."""
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await _user_from_token(creds.credentials, db)


async def get_optional_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: AsyncSession = Depends(get_db_session),
) -> Optional[User]:
    """Return the user if a valid token is present, else None (no error)."""
    if creds is None or not creds.credentials:
        return None
    try:
        return await _user_from_token(creds.credentials, db)
    except HTTPException:
        return None


def require_auth(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
):
    """Dependency that enforces auth only when settings.AUTH_REQUIRED is True.
    Used to gate business endpoints without breaking existing open access."""
    async def _dep(
        creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
        db: AsyncSession = Depends(get_db_session),
    ) -> Optional[User]:
        if not settings.AUTH_REQUIRED:
            if creds and creds.credentials:
                try:
                    return await _user_from_token(creds.credentials, db)
                except HTTPException:
                    return None
            return None
        return await get_current_user(creds, db)
    return _dep


def require_role(*roles: str):
    """RBAC dependency factory — requires an authenticated user whose role is in `roles`."""
    allowed: List[str] = list(roles)

    async def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Requires one of: {', '.join(allowed)}",
            )
        return user

    return _dep


# Convenience guards
require_admin = require_role(UserRole.ADMIN.value)
