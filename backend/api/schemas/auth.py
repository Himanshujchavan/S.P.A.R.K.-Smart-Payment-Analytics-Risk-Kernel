# api/schemas/auth.py
# Pydantic request and response models for authentication

from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

COMMON_PASSWORDS = {
    "password123",
    "password",
    "12345678",
    "qwertyuiop",
    "spark2024",
    "admin123",
    "welcome1",
    "letmein1",
}


def validate_password_complexity(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if not any(c.isdigit() for c in password):
        raise ValueError("Password must contain at least one digit.")
    if not any(c.isupper() for c in password):
        raise ValueError("Password must contain at least one uppercase letter.")
    if password.lower() in COMMON_PASSWORDS:
        raise ValueError("Password is too common. Please choose a stronger password.")
    return password


class SignupRequest(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: str
    full_name: str = Field(..., min_length=2, max_length=255)
    invite_token: Optional[str] = None
    merchant_name: Optional[str] = None  # Used if creating a new merchant

    @field_validator("email", "phone", mode="before")
    @classmethod
    def empty_identifier_to_none(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, str):
            stripped = v.strip()
            return stripped or None
        return v

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_full_name(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return validate_password_complexity(v)

    @model_validator(mode="after")
    def require_email_or_phone(self):
        if not self.email and not self.phone:
            raise ValueError("Provide an email address or a phone number.")
        return self


class LoginRequest(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: str

    @field_validator("email", "phone", mode="before")
    @classmethod
    def empty_identifier_to_none(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, str):
            stripped = v.strip()
            return stripped or None
        return v


class InviteCreateRequest(BaseModel):
    invitee_email: EmailStr
    role: str = "Risk Analyst"


class InviteResponse(BaseModel):
    invite_token: str
    expires_in_hours: int = 48


class OAuthGoogleRequest(BaseModel):
    code: str
    redirect_uri: str


class PhoneSendOTPRequest(BaseModel):
    phone: str = Field(..., pattern=r"^\+?[1-9]\d{1,14}$")


class PhoneVerifyOTPRequest(BaseModel):
    phone: str = Field(..., pattern=r"^\+?[1-9]\d{1,14}$")
    code: str = Field(..., min_length=4, max_length=10)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds


class UserResponse(BaseModel):
    user_id: UUID
    email: Optional[str] = None
    phone: Optional[str] = None
    full_name: str
    role: str
    merchant_id: Optional[UUID] = None

    model_config = {"from_attributes": True}
