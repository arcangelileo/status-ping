import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


# --- Auth Schemas ---

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    account_slug: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        if len(v) > 255:
            raise ValueError("Name must be at most 255 characters")
        return v

    @field_validator("password")
    @classmethod
    def password_strong_enough(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(v) > 128:
            raise ValueError("Password must be at most 128 characters")
        return v

    @field_validator("account_slug")
    @classmethod
    def slug_valid(cls, v: str) -> str:
        v = v.strip().lower()
        if not v or len(v) < 3:
            raise ValueError("Status page URL must be at least 3 characters")
        if len(v) > 50:
            raise ValueError("Status page URL must be at most 50 characters")
        if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", v) and len(v) > 1:
            raise ValueError("Status page URL must contain only lowercase letters, numbers, and hyphens")
        return v


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    account_slug: str
    plan: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    message: str
    user: UserResponse


# --- Monitor Schemas ---

class MonitorCreate(BaseModel):
    name: str
    url: str
    method: str = "GET"
    check_interval: int = 300
    timeout: int = 30
    expected_status_code: int = 200
    is_public: bool = True

    @field_validator("name")
    @classmethod
    def name_valid(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) < 1:
            raise ValueError("Monitor name is required")
        if len(v) > 255:
            raise ValueError("Monitor name must be at most 255 characters")
        return v

    @field_validator("url")
    @classmethod
    def url_valid(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        if len(v) > 2048:
            raise ValueError("URL must be at most 2048 characters")
        return v

    @field_validator("method")
    @classmethod
    def method_valid(cls, v: str) -> str:
        allowed = {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}
        v = v.upper().strip()
        if v not in allowed:
            raise ValueError(f"Method must be one of: {', '.join(sorted(allowed))}")
        return v

    @field_validator("check_interval")
    @classmethod
    def interval_valid(cls, v: int) -> int:
        if v < 30:
            raise ValueError("Check interval must be at least 30 seconds")
        if v > 3600:
            raise ValueError("Check interval must be at most 3600 seconds")
        return v

    @field_validator("timeout")
    @classmethod
    def timeout_valid(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Timeout must be at least 1 second")
        if v > 120:
            raise ValueError("Timeout must be at most 120 seconds")
        return v

    @field_validator("expected_status_code")
    @classmethod
    def status_code_valid(cls, v: int) -> int:
        if v < 100 or v > 599:
            raise ValueError("Expected status code must be between 100 and 599")
        return v


class MonitorUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    method: Optional[str] = None
    check_interval: Optional[int] = None
    timeout: Optional[int] = None
    expected_status_code: Optional[int] = None
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def name_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Monitor name cannot be empty")
            if len(v) > 255:
                raise ValueError("Monitor name must be at most 255 characters")
        return v

    @field_validator("url")
    @classmethod
    def url_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v.startswith(("http://", "https://")):
                raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator("method")
    @classmethod
    def method_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            allowed = {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}
            v = v.upper().strip()
            if v not in allowed:
                raise ValueError(f"Method must be one of: {', '.join(sorted(allowed))}")
        return v

    @field_validator("check_interval")
    @classmethod
    def interval_valid(cls, v: Optional[int]) -> Optional[int]:
        if v is not None:
            if v < 30:
                raise ValueError("Check interval must be at least 30 seconds")
            if v > 3600:
                raise ValueError("Check interval must be at most 3600 seconds")
        return v

    @field_validator("timeout")
    @classmethod
    def timeout_valid(cls, v: Optional[int]) -> Optional[int]:
        if v is not None:
            if v < 1:
                raise ValueError("Timeout must be at least 1 second")
            if v > 120:
                raise ValueError("Timeout must be at most 120 seconds")
        return v


class MonitorResponse(BaseModel):
    id: str
    name: str
    url: str
    method: str
    check_interval: int
    timeout: int
    expected_status_code: int
    is_active: bool
    is_public: bool
    current_status: str
    consecutive_failures: int
    last_checked_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CheckResultResponse(BaseModel):
    id: str
    monitor_id: str
    status_code: Optional[int] = None
    response_time_ms: Optional[int] = None
    status: str
    error_message: Optional[str] = None
    checked_at: datetime

    model_config = {"from_attributes": True}
