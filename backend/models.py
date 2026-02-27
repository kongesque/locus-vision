"""Pydantic models for request/response validation."""

from pydantic import BaseModel, EmailStr, field_validator
import re


# ── Request Models ───────────────────────────────────────

class UserCreate(BaseModel):
    email: str
    name: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Invalid email address")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 1:
            raise ValueError("Name cannot be empty")
        return v


class UserLogin(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class AccountUpdate(BaseModel):
    name: str | None = None
    email: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Invalid email address")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if len(v) < 1:
            raise ValueError("Name cannot be empty")
        return v


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("New password must be at least 8 characters")
        return v


class RoleUpdate(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("admin", "viewer"):
            raise ValueError("Role must be 'admin' or 'viewer'")
        return v


class AppSettingsUpdate(BaseModel):
    allow_signup: bool | None = None


# ── Response Models ──────────────────────────────────────

class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    role: str
    is_active: bool
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"


class SetupStatusResponse(BaseModel):
    needs_setup: bool


class MessageResponse(BaseModel):
    message: str


class AppSettingsResponse(BaseModel):
    allow_signup: bool



class SessionResponse(BaseModel):
    id: int
    created_at: str
    expires_at: str


class VideoTask(BaseModel):
    id: str
    filename: str
    status: str
    progress: int = 0
    created_at: str
    completed_at: str | None = None
    duration: str | None = None
    format: str | None = None
    model_name: str | None = None
    total_count: int | None = None
    zone_counts: str | None = None
    error_message: str | None = None



