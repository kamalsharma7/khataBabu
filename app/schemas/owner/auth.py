from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.core.username import normalize_login_username


class OwnerLoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return normalize_login_username(value)

    @field_validator("password")
    @classmethod
    def strip_password(cls, value: str) -> str:
        return value.strip()


class OwnerTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    must_change_password: bool


class OwnerProfileResponse(BaseModel):
    id: str
    username: str
    full_name: str
    email: str
    mobile: str
    business_id: str
    business_name: str
    business_status: str
    must_change_password: bool


class OwnerChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)
