from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    BillStatus,
    FoodType,
    KotStatus,
    OrderLineStatus,
    OrderStatus,
    OrderType,
    PaymentMethod,
    TableVisualState,
)


class OrderCreate(BaseModel):
    order_type: OrderType = OrderType.DINE_IN
    venue_table_id: Optional[UUID] = None
    guest_count: Optional[int] = Field(default=None, ge=1, le=99)
    notes: Optional[str] = None


class OrderUpdate(BaseModel):
    guest_count: Optional[int] = Field(default=None, ge=1, le=99)
    customer_name: Optional[str] = Field(default=None, max_length=128)
    customer_mobile: Optional[str] = Field(default=None, max_length=20)
    pay_later: Optional[bool] = None
    notes: Optional[str] = Field(default=None, max_length=512)
    time_duration_minutes: Optional[int] = Field(
        default=None,
        ge=1,
        le=1440,
        description="Session length in minutes (used with start anchor or now)",
    )
    time_start_now: Optional[bool] = None
    time_end_now: Optional[bool] = None
    time_session_start: Optional[datetime] = None
    time_session_end: Optional[datetime] = None
    clear_time_session: Optional[bool] = None


class OrderCancel(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=512)


class OrderTransferTable(BaseModel):
    venue_table_id: UUID


class OrderLineCreate(BaseModel):
    menu_item_id: UUID
    variation_id: Optional[UUID] = None
    quantity: int = Field(ge=1, le=99)
    addon_ids: list[UUID] = Field(default_factory=list)
    notes: Optional[str] = Field(default=None, max_length=512)


class OpenOrderLineCreate(BaseModel):
    description: str = Field(min_length=1, max_length=255)
    unit_price: Decimal = Field(gt=0)
    quantity: int = Field(default=1, ge=1, le=99)
    notes: Optional[str] = Field(default=None, max_length=512)
    menu_item_id: Optional[UUID] = Field(
        default=None,
        description="Optional menu item to link for reporting (price still uses unit_price)",
    )


class OrderLineUpdate(BaseModel):
    quantity: Optional[int] = Field(default=None, ge=1, le=99)
    notes: Optional[str] = Field(default=None, max_length=512)
    unit_price: Optional[Decimal] = Field(default=None, gt=0)


class SendKotRequest(BaseModel):
    line_ids: Optional[list[UUID]] = None
    notes: Optional[str] = Field(default=None, max_length=512)


class BillPreviewRequest(BaseModel):
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0)
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    tax_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    round_to_rupee: bool = True


class PaymentInput(BaseModel):
    method: PaymentMethod
    amount: Decimal = Field(gt=0)
    reference: Optional[str] = Field(default=None, max_length=128)


class SettleBillRequest(BillPreviewRequest):
    payments: list[PaymentInput] = Field(default_factory=list)


class AddBillPaymentRequest(PaymentInput):
    """Record a partial or full payment against an open bill."""


class SplitBillRequest(BaseModel):
    parts: int = Field(ge=2, le=20)


class SplitBillPreviewBody(BillPreviewRequest):
    parts: int = Field(ge=2, le=20)


class SplitBillPreviewResponse(BaseModel):
    parts: int
    grand_total: Decimal
    amount_per_part: Decimal


class PosBillingSettingsResponse(BaseModel):
    gst_registered: bool
    gstin: Optional[str] = None
    default_tax_percent: Decimal = Decimal("0")


class OrderLineAddonResponse(BaseModel):
    id: UUID
    name: str
    price: Decimal

    model_config = {"from_attributes": True}


class OrderLineResponse(BaseModel):
    id: UUID
    menu_item_id: Optional[UUID] = None
    is_open_item: bool = False
    menu_item_variation_id: Optional[UUID]
    item_name: str
    variation_name: Optional[str]
    quantity: int
    unit_price: Decimal
    addons_total: Decimal
    line_total: Decimal
    notes: Optional[str]
    food_type: FoodType
    status: OrderLineStatus
    addons: list[OrderLineAddonResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class KotLineResponse(BaseModel):
    id: UUID
    order_line_id: UUID
    quantity: int
    item_name: str
    variation_name: Optional[str]
    notes: Optional[str]


class KotResponse(BaseModel):
    id: UUID
    outlet_id: UUID
    order_id: UUID
    kot_number: int
    status: KotStatus
    notes: Optional[str]
    created_at: datetime
    lines: list[KotLineResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class BillPaymentResponse(BaseModel):
    id: UUID
    method: PaymentMethod
    amount: Decimal
    reference: Optional[str]

    model_config = {"from_attributes": True}


class BillResponse(BaseModel):
    id: UUID
    outlet_id: UUID
    order_id: UUID
    bill_number: int
    subtotal: Decimal
    discount_amount: Decimal
    discount_percent: Decimal
    tax_percent: Decimal
    tax_amount: Decimal
    round_off: Decimal
    grand_total: Decimal
    amount_paid: Decimal = Decimal("0")
    balance_due: Decimal = Decimal("0")
    status: BillStatus
    payments: list[BillPaymentResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class BillListEntryResponse(BillResponse):
    order_number: int
    settled_at: Optional[datetime] = None
    created_at: datetime
    table_label: Optional[str] = None
    customer_name: Optional[str] = None


class BillDetailResponse(BaseModel):
    bill: BillResponse
    order_id: UUID
    order_number: int
    order_type: OrderType
    order_created_at: datetime
    settled_at: Optional[datetime] = None
    table_label: Optional[str] = None
    customer_name: Optional[str] = None
    customer_mobile: Optional[str] = None
    guest_count: Optional[int] = None
    pay_later: bool = False
    order_notes: Optional[str] = None
    lines: list[OrderLineResponse] = Field(default_factory=list)
    kots: list[KotResponse] = Field(default_factory=list)


class OrderResponse(BaseModel):
    id: UUID
    outlet_id: UUID
    order_type: OrderType
    order_number: int
    venue_table_id: Optional[UUID]
    status: OrderStatus
    guest_count: Optional[int]
    customer_name: Optional[str] = None
    customer_mobile: Optional[str] = None
    pay_later: bool = False
    notes: Optional[str]
    created_at: datetime
    settled_at: Optional[datetime]
    time_session_start: Optional[datetime] = None
    time_session_end: Optional[datetime] = None
    time_billed_minutes: Optional[int] = None
    hourly_rate_snapshot: Optional[Decimal] = None
    time_charge: Optional[Decimal] = None
    lines: list[OrderLineResponse] = Field(default_factory=list)
    running_subtotal: Decimal = Decimal("0")

    model_config = {"from_attributes": True}


class FloorTableStatus(BaseModel):
    table_id: UUID
    area_id: UUID
    label: str
    resource_kind: str
    hourly_rate: Optional[Decimal] = None
    is_occupied: bool
    visual_state: TableVisualState = TableVisualState.BLANK
    current_order_id: Optional[UUID] = None
    order_number: Optional[int] = None
    running_total: Optional[Decimal] = None
    minutes_elapsed: Optional[int] = None
    last_kot_at: Optional[datetime] = None
    kot_count: int = 0


class FloorAreaStatus(BaseModel):
    area_id: UUID
    name: str
    billing_mode: str = "dine_in"
    operating_start: Optional[str] = None
    operating_end: Optional[str] = None
    hourly_rate: Optional[Decimal] = None
    tables: list[FloorTableStatus]


class FloorStatusResponse(BaseModel):
    areas: list[FloorAreaStatus]
