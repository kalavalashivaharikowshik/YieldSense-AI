"""Authentication helpers shared by the login endpoints."""

import logging
import math
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.core.time import utc_now_naive
from app.models.user import User

logger = logging.getLogger("yieldsense.auth")

INVALID_CREDENTIALS_MESSAGE = "Invalid email or password"

# Checked when the email is unknown, so a missing account takes about as
# long to reject as a wrong password (prevents timing-based probing).
_DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-timing")


utc_now = utc_now_naive


def ensure_not_locked(user: User) -> None:
    if user.locked_until is None:
        return

    remaining = user.locked_until - utc_now()

    if remaining.total_seconds() <= 0:
        return

    minutes = max(1, math.ceil(remaining.total_seconds() / 60))

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=(
            "Too many failed login attempts. "
            f"Please try again in {minutes} minute(s)."
        ),
        headers={"Retry-After": str(int(remaining.total_seconds()) + 1)},
    )


def record_failed_login(db: Session, user: User) -> None:
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1

    if user.failed_login_attempts >= settings.LOGIN_MAX_FAILED_ATTEMPTS:
        user.locked_until = utc_now() + timedelta(
            minutes=settings.LOGIN_LOCKOUT_MINUTES
        )
        user.failed_login_attempts = 0

        logger.warning("login_locked user_id=%s", user.id)

    db.commit()


def record_successful_login(db: Session, user: User) -> None:
    if user.failed_login_attempts or user.locked_until:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()


def issue_access_token(user: User) -> str:
    return create_access_token(
        data={
            "sub": user.email,
            "role": user.role.name,
            # Lets the API reject tokens issued before a password change.
            "ver": user.token_version or 0,
        }
    )


def revoke_user_sessions(user: User) -> None:
    """Invalidate every access token issued to the user so far."""
    user.token_version = (user.token_version or 0) + 1


def authenticate_user(
    db: Session,
    email: str,
    password: str,
    unauthorized_headers: dict[str, str] | None = None,
) -> User:
    normalized_email = email.strip().lower()

    user = (
        db.query(User)
        .filter(User.email == normalized_email)
        .first()
    )

    if not user:
        verify_password(password, _DUMMY_PASSWORD_HASH)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_CREDENTIALS_MESSAGE,
            headers=unauthorized_headers,
        )

    ensure_not_locked(user)

    if not verify_password(password, user.hashed_password):
        record_failed_login(db, user)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_CREDENTIALS_MESSAGE,
            headers=unauthorized_headers,
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before logging in",
        )

    record_successful_login(db, user)

    return user
