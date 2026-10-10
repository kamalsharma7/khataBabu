from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.platform.onboarding import _normalize_mobile


class SalesEmployeeCreate(BaseModel):
    employee_code: str = Field(min_length=2, max_length=32)
    full_name: str = Field(min_length=2, max_length=255)
    mobile: str = Field(min_length=10, max_length=20)

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, value: str) -> str:
        return _normalize_mobile(value)


class SalesEmployeeUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    mobile: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_mobile(value)


class SalesEmployeeResponse(BaseModel):
    id: UUID
    employee_code: str
    full_name: str
    mobile: str
    is_active: bool

    model_config = {"from_attributes": True}
