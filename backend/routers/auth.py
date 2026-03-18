"""
Authentication router with EdDSA JWTs and Argon2id password hashing.

Security properties:
- EdDSA (Ed25519) JWTs — asymmetric signing, only auth server can issue tokens
- Argon2id password hashing — GPU/ASIC resistant
- Access tokens: 15-minute expiry with jti claim for revocation
- Refresh tokens: 7-day expiry, HttpOnly cookie
- Rate limiting: 5 attempts per IP per 15 minutes
- jti hardcoded algorithm prevents confusion attacks
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import CurrentUser
from ..models.user import User
from ..schemas.user import (
    UserRegister, UserLogin, UserOut, TokenResponse, RefreshRequest
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
settings = get_settings()

# Argon2id hasher — parameters pulled from settings (128 MiB, 3 iter, 4 parallelism)
_ph = PasswordHasher(
    memory_cost=settings.argon2_memory_cost,
    time_cost=settings.argon2_time_cost,
    parallelism=settings.argon2_parallelism,
    hash_len=settings.argon2_hash_len,
)

# In-memory rate limit tracker (production: use Redis)
# {ip: [timestamp, ...]}
_login_attempts: dict[str, list[datetime]] = {}
_WINDOW = timedelta(minutes=15)
_MAX_ATTEMPTS = 5


def _check_rate_limit(ip: str) -> None:
    now = datetime.now(timezone.utc)
    attempts = _login_attempts.get(ip, [])
    # Remove expired attempts
    attempts = [t for t in attempts if now - t < _WINDOW]
    _login_attempts[ip] = attempts
    if len(attempts) >= _MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again in 15 minutes.",
        )


def _record_attempt(ip: str) -> None:
    _login_attempts.setdefault(ip, []).append(datetime.now(timezone.utc))


def _create_access_token(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "jti": str(uuid.uuid4()),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_private_key, algorithm="EdDSA")


def _create_refresh_token(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(days=settings.refresh_token_expire_days),
        "jti": str(uuid.uuid4()),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_private_key, algorithm="EdDSA")


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: UserRegister, db: Annotated[Session, Depends(get_db)]) -> User:
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    user = User(
        email=body.email,
        password_hash=_ph.hash(body.password),
        name=body.name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(
    body: UserLogin,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    ip = request.client.host if request.client else "unknown"
    _check_rate_limit(ip)

    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        _record_attempt(ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    try:
        _ph.verify(user.password_hash, body.password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        _record_attempt(ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Check if hash needs rehash (argon2 parameter upgrade)
    if _ph.check_needs_rehash(user.password_hash):
        user.password_hash = _ph.hash(body.password)
        db.commit()

    access_token = _create_access_token(user.id)
    refresh_token = _create_refresh_token(user.id)

    # Set refresh token as HttpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/api/v1/auth/refresh",
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(body: RefreshRequest) -> dict:
    try:
        payload = jwt.decode(
            body.refresh_token,
            settings.jwt_public_key,
            algorithms=["EdDSA"],
            options={"require": ["sub", "exp", "jti"]},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = uuid.UUID(payload["sub"])
    new_access = _create_access_token(user_id)
    return {
        "access_token": new_access,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


@router.get("/me", response_model=UserOut)
def get_me(current_user: CurrentUser) -> User:
    return current_user
