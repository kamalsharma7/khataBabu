from __future__ import annotations

import re
from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import (
    SalesBehaviorStatus,
    SalesEmploymentStatus,
    SalesProfessionalStatus,
    TenantStatus,
)
from app.schemas.platform.onboarding import _normalize_mobile

_AADHAAR_RE = re.compile(r"^\d{12}$")
_PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


def _normalize_aadhaar(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if not _AADHAAR_RE.match(digits):
        raise ValueError("Aadhaar must be 12 digits")
    return digits


def _normalize_pan(value: str) -> str:
    pan = value.strip().upper().replace(" ", "")
    if not _PAN_RE.match(pan):
        raise ValueError("PAN must be 10 characters (e.g. ABCDE1234F)")
    return pan


class SalesEmployeeCreate(BaseModel):
    employee_code: str = Field(min_length=2, max_length=32)
    full_name: str = Field(min_length=2, max_length=255)
    mobile: str = Field(min_length=10, max_length=20)
    aadhaar_number: str = Field(min_length=12, max_length=14)
    pan_number: str = Field(min_length=10, max_length=12)
    date_of_joining: date | None = None
    employment_status: SalesEmploymentStatus = SalesEmploymentStatus.ACTIVE
    behavior_status: SalesBehaviorStatus = SalesBehaviorStatus.GOOD
    professional_status: SalesProfessionalStatus = SalesProfessionalStatus.GOOD

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, value: str) -> str:
        return _normalize_mobile(value)

    @field_validator("aadhaar_number")
    @classmethod
    def validate_aadhaar(cls, value: str) -> str:
        return _normalize_aadhaar(value)

    @field_validator("pan_number")
    @classmethod
    def validate_pan(cls, value: str) -> str:
        return _normalize_pan(value)


class SalesEmployeeUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    mobile: str | None = Field(default=None, max_length=20)
    aadhaar_number: str | None = Field(default=None, max_length=14)
    pan_number: str | None = Field(default=None, max_length=12)
    date_of_joining: date | None = None
    employment_status: SalesEmploymentStatus | None = None
    behavior_status: SalesBehaviorStatus | None = None
    professional_status: SalesProfessionalStatus | None = None
    is_active: bool | None = None

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_mobile(value)

    @field_validator("aadhaar_number")
    @classmethod
    def validate_aadhaar(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_aadhaar(value)

    @field_validator("pan_number")
    @classmethod
    def validate_pan(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_pan(value)


class SalesEmployeeVenueSummary(BaseModel):
    business_id: UUID
    legal_name: str
    outlet_name: str
    outlet_ref_code: str
    status: TenantStatus
    city: str
    state: str
    created_at: str


class SalesEmployeeResponse(BaseModel):
    id: UUID
    employee_code: str
    full_name: str
    mobile: str
    aadhaar_number: str
    pan_number: str
    is_active: bool
    date_of_joining: date
    employment_status: SalesEmploymentStatus
    behavior_status: SalesBehaviorStatus
    professional_status: SalesProfessionalStatus
    venues_onboarded_count: int = 0

    model_config = {"from_attributes": True}


class SalesEmployeeDetailResponse(SalesEmployeeResponse):
    onboarded_venues: list[SalesEmployeeVenueSummary] = Field(default_factory=list)
