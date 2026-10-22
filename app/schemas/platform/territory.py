from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import TenantStatus


class TerritoryOutletRow(BaseModel):
    outlet_id: UUID
    outlet_name: str
    outlet_ref_code: str
    business_id: UUID
    legal_name: str
    city: str
    state: str
    status: TenantStatus
    plan_tier: str
    gross_sales_inr: Decimal = Field(description="Settled bill total minus refunds in selected period")
    settled_bill_count: int = 0


class TerritoryCityRow(BaseModel):
    city: str
    state: str
    outlet_count: int
    active_outlet_count: int
    gross_sales_inr: Decimal
    settled_bill_count: int
    outlets: list[TerritoryOutletRow] = Field(default_factory=list)


class TerritoryStateRow(BaseModel):
    state: str
    city_count: int
    outlet_count: int
    active_outlet_count: int
    gross_sales_inr: Decimal
    settled_bill_count: int
    cities: list[TerritoryCityRow] = Field(default_factory=list)


class TerritoryInsightRow(BaseModel):
    kind: str
    state: str
    city: str
    outlet_count: int
    gross_sales_inr: Decimal
    message: str


class TerritoryAnalyticsResponse(BaseModel):
    from_date: date | None
    to_date: date | None
    total_outlets: int
    total_states: int
    total_cities: int
    active_outlets: int
    grand_sales_inr: Decimal
    settled_bill_count: int
    states: list[TerritoryStateRow]
    insights: list[TerritoryInsightRow] = Field(default_factory=list)


class TerritoryRevenueOutletRow(BaseModel):
    outlet_id: UUID
    outlet_name: str
    outlet_ref_code: str
    business_id: UUID
    legal_name: str
    city: str
    state: str
    status: TenantStatus
    plan_tier: str
    collections_inr: Decimal = Field(description="Subscription/collection payments in selected period")
    collection_count: int = 0


class TerritoryRevenueCityRow(BaseModel):
    city: str
    state: str
    outlet_count: int
    active_outlet_count: int
    collections_inr: Decimal
    collection_count: int
    outlets: list[TerritoryRevenueOutletRow] = Field(default_factory=list)


class TerritoryRevenueStateRow(BaseModel):
    state: str
    city_count: int
    outlet_count: int
    active_outlet_count: int
    collections_inr: Decimal
    collection_count: int
    cities: list[TerritoryRevenueCityRow] = Field(default_factory=list)


class TerritoryRevenueInsightRow(BaseModel):
    kind: str
    state: str
    city: str
    outlet_count: int
    collections_inr: Decimal
    message: str


class TerritoryRevenueAnalyticsResponse(BaseModel):
    from_date: date | None
    to_date: date | None
    total_outlets: int
    total_states: int
    total_cities: int
    active_outlets: int
    grand_collections_inr: Decimal
    collection_count: int
    states: list[TerritoryRevenueStateRow]
    insights: list[TerritoryRevenueInsightRow] = Field(default_factory=list)
