from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import PaymentMethod


class AnalyticsStatusResponse(BaseModel):
    pin_configured: bool


class AnalyticsUnlockRequest(BaseModel):
    """Unlock overview: use overview PIN, or login password. First-time setup requires login password + new_pin."""

    pin: Optional[str] = Field(default=None, max_length=32)
    login_password: Optional[str] = Field(default=None, max_length=128)
    new_pin: Optional[str] = Field(default=None, max_length=32)

    @field_validator("pin", "new_pin")
    @classmethod
    def strip_optional_pin(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("login_password")
    @classmethod
    def strip_login_password(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip() or None


class AnalyticsUnlockResponse(BaseModel):
    analytics_token: str
    expires_in_minutes: int
    pin_configured: bool


class AnalyticsPaymentBreakdown(BaseModel):
    method: PaymentMethod
    amount: Decimal
    count: int


class AnalyticsSummaryResponse(BaseModel):
    from_datetime: datetime
    to_datetime: datetime
    gross_sales: Decimal
    total_collected: Decimal
    discount_total: Decimal
    tax_total: Decimal
    orders_settled: int
    orders_cancelled: int
    average_bill: Decimal
    pay_later_settled: int
    open_orders_now: int
    payment_breakdown: list[AnalyticsPaymentBreakdown]


class AnalyticsOrderRow(BaseModel):
    order_id: UUID
    order_number: int
    bill_number: int
    settled_at: datetime
    table_label: Optional[str] = None
    customer_name: Optional[str] = None
    guest_count: Optional[int] = None
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    grand_total: Decimal
    pay_later: bool
    payments_summary: str


class AnalyticsOrdersResponse(BaseModel):
    total: int
    items: list[AnalyticsOrderRow]
