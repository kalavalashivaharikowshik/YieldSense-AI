import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

PASSWORD_MIN_LENGTH = 8
# bcrypt only uses the first 72 bytes of a password, so longer values are
# rejected instead of being silently truncated.
PASSWORD_MAX_BYTES = 72

PHONE_PATTERN = re.compile(r"^\+?[0-9]{7,15}$")


def validate_password_strength(value: str) -> str:
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Password must be at least {PASSWORD_MIN_LENGTH} characters long"
        )

    if len(value.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise ValueError(
            f"Password must be at most {PASSWORD_MAX_BYTES} bytes long"
        )

    if not value.strip():
        raise ValueError("Password cannot be only spaces")

    return value


def normalize_full_name(value: str) -> str:
    cleaned = " ".join(value.split())

    if len(cleaned) < 2:
        raise ValueError("Full name must be at least 2 characters long")

    if len(cleaned) > 100:
        raise ValueError("Full name must be at most 100 characters long")

    return cleaned


def normalize_phone(value: str | None) -> str | None:
    if value is None:
        return None

    # Allow common separators in input, but store digits only.
    cleaned = re.sub(r"[\s\-().]", "", value)

    if not cleaned:
        return None

    if not PHONE_PATTERN.match(cleaned):
        raise ValueError(
            "Phone number must contain 7 to 15 digits, "
            "optionally starting with +"
        )

    return cleaned


class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    phone: str | None = None
    password: str

    @field_validator("full_name")
    @classmethod
    def check_full_name(cls, value):
        return normalize_full_name(value)
    @field_validator("phone")
    @classmethod
    def check_phone(cls, value):
        return normalize_phone(value)
    @field_validator("password")
    @classmethod
    def check_password(cls, value):
        return validate_password_strength(value)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr

    otp_code: str = Field(
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
    )

    new_password: str

    @field_validator("new_password")
    @classmethod
    def check_password(cls, value):
        return validate_password_strength(value)


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    phone: str | None = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return normalize_full_name(value)

    @field_validator("phone")
    @classmethod
    def check_phone(cls, value):
        return normalize_phone(value)


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(max_length=256)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def check_password(cls, value):
        return validate_password_strength(value)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    phone: str | None
    role: str
    is_active: bool
    is_verified: bool


class UserProfileResponse(UserResponse):
    pass


class MessageResponse(BaseModel):
    message: str


class RegisterResponse(BaseModel):
    message: str
    email: EmailStr


class SendOTPRequest(BaseModel):
    email: EmailStr


class VerifyOTPRequest(BaseModel):
    email: EmailStr

    otp_code: str = Field(
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
    )
