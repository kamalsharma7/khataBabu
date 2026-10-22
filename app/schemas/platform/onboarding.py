from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.data.india_territory import validate_state_city
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

    @model_validator(mode="after")
    def normalize_territory(self) -> "BusinessOnboardingInput":
        state, city = validate_state_city(self.state, self.city)
        self.state = state
        self.city = city
        return self


class TenantOnboardingCreateRequest(BaseModel):
    business: BusinessOnboardingInput
    owner: OwnerOnboardingInput
    outlet: OutletOnboardingInput
    assigned_sales_employee_id: UUID | None = None


class OwnerCredentialsOnce(BaseModel):
    username: str
    temporary_password: str
    must_change_password: bool = True
    role: str = Field(description="owner | admin | employee")


class TenantOnboardingCreateResponse(BaseModel):
    business_id: UUID
    outlet_id: UUID
    owner_id: UUID
    outlet_ref_code: str
    status: TenantStatus
    owner_credentials: OwnerCredentialsOnce
    staff_credentials: list[OwnerCredentialsOnce] = Field(default_factory=list)
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


class TenantOwnerSummary(BaseModel):
    id: UUID
    full_name: str
    email: str
    mobile: str
    username: str
    role: str


class TenantDetailResponse(BaseModel):
    business_id: UUID
    outlet_id: UUID
    status: TenantStatus
    legal_name: str
    business_type: BusinessType
    primary_phone: str
    primary_email: str
    city: str
    state: str
    gst_registered: bool
    gstin: Optional[str]
    fssai: Optional[str]
    pan: Optional[str]
    plan_tier: PlanTier
    internal_notes: Optional[str]
    assigned_sales_employee_id: UUID | None
    assigned_sales_employee_name: str | None = None
    outlet_name: str
    address_line: str
    pincode: str
    outlet_phone: Optional[str]
    operating_models: list[OperatingModel]
    venue_kinds: list[VenueKind]
    time_based_billing_enabled: bool
    rough_scale_notes: Optional[str]
    outlet_ref_code: str
    owner: TenantOwnerSummary
    created_at: str


class TenantUpdateRequest(BaseModel):
    legal_name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    business_type: Optional[BusinessType] = None
    primary_phone: Optional[str] = None
    primary_email: Optional[EmailStr] = None
    city: Optional[str] = Field(default=None, min_length=2, max_length=128)
    state: Optional[str] = Field(default=None, min_length=2, max_length=128)
    gst_registered: Optional[bool] = None
    gstin: Optional[str] = Field(default=None, max_length=15)
    fssai: Optional[str] = Field(default=None, max_length=32)
    pan: Optional[str] = Field(default=None, max_length=10)
    plan_tier: Optional[PlanTier] = None
    internal_notes: Optional[str] = Field(default=None, max_length=2000)
    assigned_sales_employee_id: UUID | None = None
    outlet_name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    address_line: Optional[str] = Field(default=None, min_length=5, max_length=512)
    pincode: Optional[str] = Field(default=None, min_length=6, max_length=12)
    outlet_phone: Optional[str] = None
    operating_models: Optional[list[OperatingModel]] = None
    venue_kinds: Optional[list[VenueKind]] = None
    time_based_billing_enabled: Optional[bool] = None
    rough_scale_notes: Optional[str] = Field(default=None, max_length=512)
    owner_full_name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    owner_email: Optional[EmailStr] = None
    owner_mobile: Optional[str] = None

    @field_validator("primary_phone")
    @classmethod
    def validate_primary_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _normalize_mobile(value)

    @field_validator("owner_mobile")
    @classmethod
    def validate_owner_mobile(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _normalize_mobile(value)

    @field_validator("outlet_phone")
    @classmethod
    def validate_outlet_phone_patch(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value.strip() == "":
            return None
        return _normalize_mobile(value)

    @model_validator(mode="after")
    def normalize_territory(self) -> "TenantUpdateRequest":
        if self.state is None and self.city is None:
            return self
        if self.state is None or self.city is None:
            raise ValueError("City and state must be updated together")
        state, city = validate_state_city(self.state, self.city)
        self.state = state
        self.city = city
        return self


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
