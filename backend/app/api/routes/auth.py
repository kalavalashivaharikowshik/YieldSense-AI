import logging
from functools import partial

import anyio
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.security import (
    hash_password,
    verify_password,
)
from app.db.database import get_db
from app.models.user import EmailOTP, Role, User
from app.schemas.auth import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    SendOTPRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserProfileResponse,
    VerifyOTPRequest,
)
from app.services.auth_service import (
    authenticate_user,
    issue_access_token,
    revoke_user_sessions,
)
from app.services.email_service import (
    EmailDeliveryError,
    send_password_reset_otp_email,
    send_verification_otp_email,
)
from app.services.otp_service import (
    EMAIL_VERIFICATION_PURPOSE,
    PASSWORD_RESET_PURPOSE,
    create_otp,
    verify_otp,
)

logger = logging.getLogger(__name__)

# The same responses are returned whether or not an account exists, so
# these endpoints cannot be used to find out which emails are registered.
PASSWORD_RESET_SENT_MESSAGE = (
    "If an account exists for this email, a password reset code has been sent."
)
VERIFICATION_SENT_MESSAGE = (
    "If this email belongs to an unverified account, "
    "a verification code has been sent."
)
NO_ACTIVE_OTP_MESSAGE = "No active OTP was found. Please request a new OTP."

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)


def send_email_from_worker_thread(send_function, user: User, otp_code: str) -> None:
    """Run an async email sender from a sync endpoint.

    These endpoints are plain functions so FastAPI runs them in its
    thread pool; database work then no longer blocks the event loop that
    serves every other request.
    """
    anyio.from_thread.run(
        partial(
            send_function,
            recipient_email=user.email,
            recipient_name=user.full_name,
            otp_code=otp_code,
        )
    )


def deactivate_latest_otp_after_email_failure(
    db: Session,
    user_id: int,
    purpose: str,
) -> None:
    otp_record = (
        db.query(EmailOTP)
        .filter(
            EmailOTP.user_id == user_id,
            EmailOTP.purpose == purpose,
            EmailOTP.is_active.is_(True),
        )
        .order_by(EmailOTP.created_at.desc())
        .first()
    )

    if otp_record:
        otp_record.is_active = False
        db.commit()

@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    normalized_email = request.email.strip().lower()
    normalized_phone = request.phone

    existing_user = (
        db.query(User)
        .filter(User.email == normalized_email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address is already registered",
        )

    if normalized_phone:
        existing_phone = (
            db.query(User)
            .filter(User.phone == normalized_phone)
            .first()
        )

        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number is already registered",
            )

    farmer_role = (
        db.query(Role)
        .filter(Role.name == "farmer")
        .first()
    )

    if not farmer_role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Default farmer role is not configured",
        )

    user = User(
        full_name=request.full_name,
        email=normalized_email,
        phone=normalized_phone,
        hashed_password=hash_password(request.password),
        role_id=farmer_role.id,
        is_active=True,
        is_verified=False,
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except Exception as error:
        db.rollback()

        logger.exception(
            "registration_database_failed email=%s",
            normalized_email,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create account",
        ) from error

    try:
        otp_code = create_otp(
            db=db,
            user=user,
            purpose=EMAIL_VERIFICATION_PURPOSE,
        )

        send_email_from_worker_thread(
            send_verification_otp_email,
            user,
            otp_code,
        )

    except EmailDeliveryError as error:
        deactivate_latest_otp_after_email_failure(
            db=db,
            user_id=user.id,
            purpose=EMAIL_VERIFICATION_PURPOSE,
        )

        logger.error(
            "registration_verification_email_failed user_id=%s",
            user.id,
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Your account was created, but the verification "
                "email could not be sent. Please use resend OTP."
            ),
        ) from error

    return {
        "message": (
            "Registration successful. "
            "A verification OTP was sent to your email."
        ),
        "email": user.email,
    }

@router.post("/login", response_model=TokenResponse)
def login_user(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    user = authenticate_user(
        db=db,
        email=request.email,
        password=request.password,
    )

    return {
        "access_token": issue_access_token(user),
        "token_type": "bearer",
    }


@router.post("/token", response_model=TokenResponse)
def swagger_token_login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """OAuth2 form login used by the Swagger UI 'Authorize' button."""
    user = authenticate_user(
        db=db,
        email=form_data.username,
        password=form_data.password,
        unauthorized_headers={"WWW-Authenticate": "Bearer"},
    )

    return {
        "access_token": issue_access_token(user),
        "token_type": "bearer",
    }


@router.post("/logout")
def logout_user():
    return {
        "message": "Logout successful. Please remove token from client storage."
    }


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
)
def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    normalized_email = request.email.strip().lower()

    user = (
        db.query(User)
        .filter(User.email == normalized_email)
        .first()
    )

    if not user or not user.is_active:
        logger.info("password_reset_requested_for_unknown_or_inactive_account")

        return {"message": PASSWORD_RESET_SENT_MESSAGE}

    otp_code = create_otp(
        db=db,
        user=user,
        purpose=PASSWORD_RESET_PURPOSE,
    )

    try:
        send_email_from_worker_thread(
            send_password_reset_otp_email,
            user,
            otp_code,
        )

    except EmailDeliveryError as error:
        deactivate_latest_otp_after_email_failure(
            db=db,
            user_id=user.id,
            purpose=PASSWORD_RESET_PURPOSE,
        )

        logger.error(
            "password_reset_email_failed user_id=%s",
            user.id,
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The password reset email could not be delivered. "
                "Please try again."
            ),
        ) from error

    return {"message": PASSWORD_RESET_SENT_MESSAGE}
@router.post(
    "/reset-password",
    response_model=MessageResponse,
)
def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    normalized_email = request.email.strip().lower()

    user = (
        db.query(User)
        .filter(User.email == normalized_email)
        .first()
    )

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=NO_ACTIVE_OTP_MESSAGE,
        )

    verify_otp(
        db=db,
        user=user,
        purpose=PASSWORD_RESET_PURPOSE,
        otp_code=request.otp_code,
    )

    user.hashed_password = hash_password(
        request.new_password
    )
    revoke_user_sessions(user)

    db.commit()

    return {
        "message": "Password reset successfully",
    }

@router.get(
    "/me",
    response_model=UserProfileResponse,
)
def get_me(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": current_user.id,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "phone": current_user.phone,
        "role": current_user.role.name,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
    }
    
@router.put("/profile", response_model=UserProfileResponse)
def update_profile(
    request: UpdateProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    if request.full_name is not None:
        current_user.full_name = request.full_name

    if request.phone is not None and request.phone != current_user.phone:
        phone_in_use = (
            db.query(User.id)
            .filter(
                User.phone == request.phone,
                User.id != current_user.id,
            )
            .first()
        )

        if phone_in_use:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number is already registered",
            )

        current_user.phone = request.phone

    db.commit()
    db.refresh(current_user)

    return {
        "id": current_user.id,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "phone": current_user.phone,
        "role": current_user.role.name,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified
    }

@router.post(
    "/send-otp",
    response_model=MessageResponse,
)
def send_verification_otp(
    request: SendOTPRequest,
    db: Session = Depends(get_db),
):
    normalized_email = request.email.strip().lower()

    user = (
        db.query(User)
        .filter(User.email == normalized_email)
        .first()
    )

    if not user or user.is_verified or not user.is_active:
        return {"message": VERIFICATION_SENT_MESSAGE}

    otp_code = create_otp(
        db=db,
        user=user,
        purpose=EMAIL_VERIFICATION_PURPOSE,
    )

    try:
        send_email_from_worker_thread(
            send_verification_otp_email,
            user,
            otp_code,
        )

    except EmailDeliveryError as error:
        deactivate_latest_otp_after_email_failure(
            db=db,
            user_id=user.id,
            purpose=EMAIL_VERIFICATION_PURPOSE,
        )

        logger.error(
            "verification_email_delivery_failed user_id=%s",
            user.id,
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The verification email could not be delivered. "
                "Please try again."
            ),
        ) from error

    return {"message": VERIFICATION_SENT_MESSAGE}

@router.post(
    "/verify-otp",
    response_model=MessageResponse,
)
def verify_email_otp(
    request: VerifyOTPRequest,
    db: Session = Depends(get_db),
):
    normalized_email = request.email.strip().lower()

    user = (
        db.query(User)
        .filter(User.email == normalized_email)
        .first()
    )

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=NO_ACTIVE_OTP_MESSAGE,
        )

    if user.is_verified:
        return {
            "message": "Email address is already verified",
        }

    verify_otp(
        db=db,
        user=user,
        purpose=EMAIL_VERIFICATION_PURPOSE,
        otp_code=request.otp_code,
    )

    user.is_verified = True

    db.commit()
    db.refresh(user)

    return {
        "message": "Email verified successfully",
    }

@router.post("/change-password", response_model=ChangePasswordResponse)
def change_password(
    request: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(
        request.old_password,
        current_user.hashed_password,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Old password is incorrect",
        )

    current_user.hashed_password = hash_password(
        request.new_password
    )
    revoke_user_sessions(current_user)

    db.commit()
    db.refresh(current_user)

    # Every older token is now invalid, so hand this session a fresh one.
    return {
        "message": "Password changed successfully",
        "access_token": issue_access_token(current_user),
        "token_type": "bearer",
    }

@router.get("/admin-only")
def admin_only(
    current_user: User = Depends(require_role("admin"))
):
    return {
        "message": "Welcome Admin. You have access to this protected route."
    }


@router.get("/farmer-only")
def farmer_only(
    current_user: User = Depends(require_role("farmer"))
):
    return {
        "message": "Welcome Farmer. You have access to this protected route."
    }