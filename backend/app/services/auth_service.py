"""Authentication helpers shared by the login endpoints."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.models.user import User

INVALID_CREDENTIALS_MESSAGE = "Invalid email or password"


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

    if not user or not verify_password(password, user.hashed_password):
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

    return user
