from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class BusinessSettingsResponse(BaseModel):
    legal_name: str
    trading_name: str | None = None
    primary_phone: str
    primary_email: str
    city: str
    state: str
    gst_registered: bool
    gstin: str | None = None
    fssai: str | None = None
    pan: str | None = None
    registered_address: str | None = None
    invoice_prefix: str
    worker_max_discount_percent: Decimal
    max_discount_percent: Decimal
    manager_pin_configured: bool


class BusinessProfileUpdate(BaseModel):
    legal_name: str | None = Field(default=None, max_length=255)
    trading_name: str | None = Field(default=None, max_length=255)
    primary_phone: str | None = Field(default=None, max_length=20)
    primary_email: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=128)
    state: str | None = Field(default=None, max_length=128)
    gst_registered: bool | None = None
    gstin: str | None = Field(default=None, max_length=15)
    fssai: str | None = Field(default=None, max_length=32)
    pan: str | None = Field(default=None, max_length=10)
    registered_address: str | None = Field(default=None, max_length=512)
    invoice_prefix: str | None = Field(default=None, max_length=16)


class PosPolicyUpdate(BaseModel):
    worker_max_discount_percent: Decimal = Field(ge=0, le=100)
    max_discount_percent: Decimal = Field(ge=0, le=100)


class ManagerPinUpdate(BaseModel):
    pin: str = Field(min_length=4, max_length=12)


class DiscountPolicyResponse(BaseModel):
    worker_max_discount_percent: Decimal
    max_discount_percent: Decimal
    manager_pin_configured: bool


class AuditLogEntryResponse(BaseModel):
    id: str
    outlet_id: str | None
    actor_username: str | None
    action: str
    entity_type: str
    entity_id: str | None
    summary: str
    reason: str | None
    created_at: str


class AuditLogListResponse(BaseModel):
    items: list[AuditLogEntryResponse]


class CashMovementCreate(BaseModel):
    kind: str = Field(pattern="^(expense|withdrawal|deposit)$")
    amount: Decimal = Field(gt=0)
    reason: str = Field(min_length=1, max_length=512)


class OpenBusinessDayRequest(BaseModel):
    opening_cash: Decimal = Field(ge=0)


class CloseBusinessDayRequest(BaseModel):
    actual_closing_cash: Decimal = Field(ge=0)
    notes: str | None = Field(default=None, max_length=1024)


class CashMovementResponse(BaseModel):
    id: str
    kind: str
    amount: Decimal
    reason: str
    created_at: str


class BusinessDayResponse(BaseModel):
    id: str
    business_date: str
    status: str
    opening_cash: Decimal
    expected_cash: Decimal | None
    projected_expected_cash: Decimal
    actual_closing_cash: Decimal | None
    cash_variance: Decimal | None
    cash_sales_total: Decimal
    notes: str | None
    movements: list[CashMovementResponse]


class RefundCreateRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    method: str = Field(min_length=1, max_length=32)
    reason: str = Field(min_length=3, max_length=512)
    manager_approval_pin: str | None = Field(default=None, max_length=12)


class RefundResponse(BaseModel):
    id: str
    bill_id: str
    amount: Decimal
    method: str
    reason: str
    refunded_total: Decimal
    bill_grand_total: Decimal
    created_at: str
