"""Pydantic schemas used for request validation and response serialization."""

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# Sybase login names: letters, digits, underscore, max 30 chars (ASE identifier limit)
LOGIN_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,29}$")


class LoginRequest(BaseModel):
    """Credentials submitted on the login form."""

    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=256)

    @field_validator("username")
    @classmethod
    def strip_username(cls, v: str) -> str:
        return v.strip()


class UnlockRequest(BaseModel):
    """Form payload for an unlock request, fully validated server-side."""

    server_name: str = Field(..., min_length=1, max_length=128)
    login_name: str = Field(..., min_length=1, max_length=30)
    reason: str = Field(..., min_length=10, max_length=500)

    @field_validator("login_name")
    @classmethod
    def validate_login_name(cls, v: str) -> str:
        v = v.strip()
        if not LOGIN_NAME_PATTERN.match(v):
            raise ValueError(
                "Login name must start with a letter and contain only letters, "
                "digits, or underscores (max 30 characters)."
            )
        return v

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        v = v.strip()
        # Reject obvious script/HTML injection attempts in free-text field.
        if re.search(r"<\s*script|javascript:|on\w+\s*=", v, re.IGNORECASE):
            raise ValueError("Reason field contains disallowed content.")
        return v

    @field_validator("server_name")
    @classmethod
    def strip_server(cls, v: str) -> str:
        return v.strip()


class UnlockResult(BaseModel):
    """Outcome returned to the UI after attempting an unlock."""

    success: bool
    message: str
    login_name: str
    server_name: str
    execution_time_ms: float


class AuditEntry(BaseModel):
    """Read model for displaying audit history."""

    id: int
    timestamp: datetime
    requester: str
    server: str
    login_name: str
    reason: str
    status: str
    message: str
    execution_time_ms: float
    client_ip: str

    model_config = {"from_attributes": True}
