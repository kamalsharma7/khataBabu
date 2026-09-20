from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class PlatformLoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()


class PlatformTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class PlatformAdminProfile(BaseModel):
    id: str
    username: str
    mobile: str

    model_config = {"from_attributes": True}
