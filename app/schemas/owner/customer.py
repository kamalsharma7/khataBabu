from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import CustomerRelation, OrderType, PaymentMethod

CUSTOMER_SEGMENTS = ("new", "occasional", "regular", "vip", "at_risk", "lost", "prospect")
SEGMENT_PATTERN = "^(all|new|occasional|regular|vip|at_risk|lost|prospect)$"
SORT_PATTERN = "^(last_visit|visits|spend|name|created)$"


class CustomerBase(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=255)
    locality: Optional[str] = Field(default=None, max_length=255)
    address: Optional[str] = Field(default=None, max_length=1024)
    birthday: Optional[date] = None
    anniversary: Optional[date] = None
    relation: Optional[CustomerRelation] = None
    tags: list[str] = Field(default_factory=list)
    notes: Optional[str] = Field(default=None, max_length=2048)
    marketing_opt_in: bool = True


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=255)
    locality: Optional[str] = Field(default=None, max_length=255)
    address: Optional[str] = Field(default=None, max_length=1024)
    birthday: Optional[date] = None
    anniversary: Optional[date] = None
    relation: Optional[CustomerRelation] = None
    tags: Optional[list[str]] = None
    notes: Optional[str] = Field(default=None, max_length=2048)
    marketing_opt_in: Optional[bool] = None
    clear_birthday: bool = False
    clear_anniversary: bool = False


class CustomerSummary(BaseModel):
    id: UUID
    outlet_id: UUID
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    locality: Optional[str] = None
    relation: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    birthday: Optional[date] = None
    anniversary: Optional[date] = None
    marketing_opt_in: bool = True
    source: str = "pos"
    visit_count: int = 0
    total_spend_inr: Decimal = Decimal("0")
    avg_ticket_inr: Decimal = Decimal("0")
    first_visit_at: Optional[datetime] = None
    last_visit_at: Optional[datetime] = None
    days_since_last_visit: Optional[int] = None
    segment: str = "prospect"
    khata_due_inr: Decimal = Decimal("0")
    created_at: datetime


class CustomerFavouriteItem(BaseModel):
    item_name: str
    times_ordered: int
    total_qty: int
    menu_item_id: Optional[UUID] = None


class CustomerVisit(BaseModel):
    order_id: UUID
    order_number: int
    bill_id: Optional[UUID] = None
    bill_number: Optional[int] = None
    invoice_code: Optional[str] = None
    order_type: OrderType
    table_label: Optional[str] = None
    settled_at: Optional[datetime] = None
    grand_total: Decimal = Decimal("0")
    items_summary: str = ""
    payment_methods: list[PaymentMethod] = Field(default_factory=list)
    guest_count: Optional[int] = None


class WeekdayCount(BaseModel):
    weekday: int  # 0 = Monday
    label: str
    visits: int


class DaypartCount(BaseModel):
    key: str
    label: str
    visits: int


class PaymentMixEntry(BaseModel):
    method: PaymentMethod
    amount_inr: Decimal
    share_percent: Decimal


class CustomerDetail(CustomerSummary):
    address: Optional[str] = None
    notes: Optional[str] = None
    preferred_order_type: Optional[OrderType] = None
    veg_share_percent: Optional[Decimal] = None
    avg_guest_count: Optional[Decimal] = None
    favourite_items: list[CustomerFavouriteItem] = Field(default_factory=list)
    visits_by_weekday: list[WeekdayCount] = Field(default_factory=list)
    visits_by_daypart: list[DaypartCount] = Field(default_factory=list)
    payment_mix: list[PaymentMixEntry] = Field(default_factory=list)
    recent_visits: list[CustomerVisit] = Field(default_factory=list)
    avg_days_between_visits: Optional[Decimal] = None


class CustomerListResponse(BaseModel):
    total: int
    customers: list[CustomerSummary]


class CustomerLookupResponse(BaseModel):
    found: bool
    customer: Optional[CustomerSummary] = None
    favourite_items: list[str] = Field(default_factory=list)
    greeting: Optional[str] = None


class SegmentCount(BaseModel):
    segment: str
    label: str
    customers: int
    spend_inr: Decimal = Decimal("0")


class LocalityInsight(BaseModel):
    locality: str
    customers: int
    visits: int
    spend_inr: Decimal


class FrequencyBucket(BaseModel):
    bucket: str
    customers: int


class MonthlyNewCustomers(BaseModel):
    month: str  # YYYY-MM
    label: str
    customers: int


class TrendingItem(BaseModel):
    item_name: str
    customers: int
    total_qty: int


class OccasionEntry(BaseModel):
    customer_id: UUID
    name: Optional[str]
    phone: Optional[str]
    occasion: str  # birthday | anniversary
    on_date: date
    days_away: int


class OrderTypeMix(BaseModel):
    order_type: OrderType
    visits: int
    share_percent: Decimal


class CrmInsightsResponse(BaseModel):
    total_customers: int
    with_phone: int
    new_this_month: int
    new_last_month: int
    repeat_customers: int
    repeat_rate_percent: Decimal
    avg_visits_per_customer: Decimal
    avg_spend_per_customer_inr: Decimal
    identified_orders_30d: int
    settled_orders_30d: int
    capture_rate_30d_percent: Decimal
    khata_due_total_inr: Decimal
    segments: list[SegmentCount]
    top_localities: list[LocalityInsight]
    top_spenders: list[CustomerSummary]
    most_frequent: list[CustomerSummary]
    win_back: list[CustomerSummary]
    frequency_buckets: list[FrequencyBucket]
    monthly_new: list[MonthlyNewCustomers]
    trending_items: list[TrendingItem]
    upcoming_occasions: list[OccasionEntry]
    order_type_mix: list[OrderTypeMix]
    visits_by_weekday: list[WeekdayCount]
    visits_by_daypart: list[DaypartCount]


class CustomerBackfillResponse(BaseModel):
    orders_scanned: int
    orders_linked: int
    customers_created: int
    customers_refreshed: int
