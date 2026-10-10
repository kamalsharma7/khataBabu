from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class InventoryItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    unit: str = Field(default="pcs", max_length=32)
    opening_stock: Decimal = Field(default=Decimal("0"), ge=0)
    low_stock_threshold: Decimal | None = Field(default=None, ge=0)


class InventoryItemUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    unit: str | None = Field(default=None, max_length=32)
    low_stock_threshold: Decimal | None = None
    adjust_stock_delta: Decimal | None = None
    adjustment_notes: str | None = Field(default=None, max_length=512)


class InventoryItemResponse(BaseModel):
    id: UUID
    outlet_id: UUID
    name: str
    unit: str
    current_stock: Decimal
    low_stock_threshold: Decimal | None

    model_config = {"from_attributes": True}


class MenuInventoryLinkInput(BaseModel):
    inventory_item_id: UUID
    qty_per_serve: Decimal = Field(gt=0)


class InventoryDayBucket(BaseModel):
    label: str
    total_qty: Decimal


class InventoryAnalyticsResponse(BaseModel):
    items: list[InventoryItemResponse]
    usage_by_weekday: list[InventoryDayBucket]
    usage_by_month: list[InventoryDayBucket]
