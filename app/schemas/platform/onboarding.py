from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models.enums import BusinessType, OperatingModel, PlanTier, TenantStatus, VenueKind


def _normalize_mobile(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) == 10:
        return f"+91{digits}"
    if digits.startswith("91") and len(digits) == 12:
        return f"+{digits}"
    if value.startswith("+") and len(digits) >= 10:
        return f"+{digits}"
    raise ValueError("Invalid mobile number")


class OwnerOnboardingInput(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    mobile: str = Field(min_length=10, max_length=20)

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, value: str) -> str:
        return _normalize_mobile(value)


class OutletOnboardingInput(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    address_line: str = Field(min_length=5, max_length=512)
    pincode: str = Field(min_length=6, max_length=12)
    outlet_phone: Optional[str] = None
    operating_models: list[OperatingModel] = Field(min_length=1)
    venue_kinds: list[VenueKind] = Field(min_length=1)
    time_based_billing_enabled: bool = False
    rough_scale_notes: Optional[str] = Field(default=None, max_length=512)

    @field_validator("outlet_phone")
    @classmethod
    def validate_outlet_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value.strip() == "":
            return None
        return _normalize_mobile(value)


class BusinessOnboardingInput(BaseModel):
    legal_name: str = Field(min_length=2, max_length=255)
    business_type: BusinessType
    primary_phone: str
    primary_email: EmailStr
    city: str = Field(min_length=2, max_length=128)
    state: str = Field(min_length=2, max_length=128)
    gst_registered: bool = False
    gstin: Optional[str] = Field(default=None, max_length=15)
    fssai: Optional[str] = Field(default=None, max_length=32)
    pan: Optional[str] = Field(default=None, max_length=10)
    plan_tier: PlanTier = PlanTier.BASIC
    internal_notes: Optional[str] = Field(default=None, max_length=2000)
    activate_immediately: bool = True

    @field_validator("primary_phone")
    @classmethod
    def validate_primary_phone(cls, value: str) -> str:
        return _normalize_mobile(value)

    @field_validator("gstin")
    @classmethod
    def validate_gstin(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip().upper()
        if len(cleaned) != 15:
            raise ValueError("GSTIN must be 15 characters")
        return cleaned

    @model_validator(mode="after")
    def gstin_required_when_registered(self) -> "BusinessOnboardingInput":
        if self.gst_registered and not self.gstin:
            raise ValueError("GSTIN is required when gst_registered is true")
        return self


class TenantOnboardingCreateRequest(BaseModel):
    business: BusinessOnboardingInput
    owner: OwnerOnboardingInput
    outlet: OutletOnboardingInput


class OwnerCredentialsOnce(BaseModel):
    username: str
    temporary_password: str
    must_change_password: bool = True


class TenantOnboardingCreateResponse(BaseModel):
    business_id: UUID
    outlet_id: UUID
    owner_id: UUID
    outlet_ref_code: str
    status: TenantStatus
    owner_credentials: OwnerCredentialsOnce
    message: str = (
        "Share owner credentials securely once. Temporary password is not stored in plain text "
        "and cannot be retrieved again."
    )


class TenantSummary(BaseModel):
    business_id: UUID
    legal_name: str
    status: TenantStatus
    plan_tier: PlanTier
    primary_email: str
    city: str
    state: str
    outlet_ref_code: str
    outlet_name: str
    created_at: str

    model_config = {"from_attributes": True}


class TenantStatusUpdateRequest(BaseModel):
    status: TenantStatus
    confirm_username: Optional[str] = Field(default=None, min_length=3, max_length=64)
    confirm_password: Optional[str] = Field(default=None, min_length=8, max_length=128)

    @model_validator(mode="after")
    def suspend_requires_reauth(self) -> "TenantStatusUpdateRequest":
        if self.status == TenantStatus.SUSPENDED:
            if not self.confirm_username or not self.confirm_password:
                raise ValueError(
                    "confirm_username and confirm_password are required to suspend a venue",
                )
        return self
