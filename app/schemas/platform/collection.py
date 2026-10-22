from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import TenantStatus


class CollectionCreate(BaseModel):
    business_id: UUID
    amount_inr: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    payment_date: date | None = None
    next_payment_date: date
    tenure_months: int = Field(ge=1, le=120)
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def next_after_payment(self) -> CollectionCreate:
        payment = self.payment_date or date.today()
        if self.next_payment_date < payment:
            raise ValueError("next_payment_date must be on or after payment_date")
        return self


class CollectionResponse(BaseModel):
    id: UUID
    business_id: UUID
    amount_inr: Decimal
    payment_date: date
    next_payment_date: date
    tenure_months: int
    notes: str | None
    recorded_by_admin_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CollectionVenueOption(BaseModel):
    business_id: UUID
    legal_name: str
    outlet_name: str
    outlet_ref_code: str
    city: str
    state: str
    status: TenantStatus
    joining_date: date


class CollectionCallingRow(BaseModel):
    business_id: UUID
    legal_name: str
    outlet_name: str
    outlet_ref_code: str
    city: str
    state: str
    status: TenantStatus
    owner_name: str | None = None
    owner_mobile: str | None = None
    venue_phone: str
    amount_inr: Decimal
    tenure_months: int
    payment_date: date
    next_payment_date: date
    days_until_due: int
    is_overdue: bool
    collection_id: UUID


class RestaurantCollectionRow(BaseModel):
    business_id: UUID
    legal_name: str
    outlet_name: str
    outlet_ref_code: str
    city: str
    state: str
    status: TenantStatus
    joining_date: date
    plan_tier: str
    has_collection: bool
    latest_amount_inr: Decimal | None = None
    tenure_months: int | None = None
    latest_payment_date: date | None = None
    next_payment_date: date | None = None
    total_collected_inr: Decimal
    pack_count: int


class CollectionCallingList(BaseModel):
    as_of: date
    due_within_days: int
    rows: list[CollectionCallingRow]


class RestaurantCollectionList(BaseModel):
    rows: list[RestaurantCollectionRow]


class CollectionHistoryResponse(BaseModel):
    business_id: UUID
    legal_name: str
    outlet_name: str
    outlet_ref_code: str
    city: str
    state: str
    joining_date: date
    total_collected_inr: Decimal
    entries: list[CollectionResponse]
