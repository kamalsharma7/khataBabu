from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class InventoryItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    unit: str = Field(default="pcs", max_length=32)
    daily_par: Decimal | None = Field(default=None, ge=0)
    tracks_daily: bool = True
    category: str = Field(default="grocery", max_length=64)
    cost_per_unit: Decimal | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=512)
    low_stock_threshold: Decimal | None = Field(default=None, ge=0)
    opening_stock: Decimal = Field(default=Decimal("0"), ge=0)


class InventoryItemUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    unit: str | None = Field(default=None, max_length=32)
    daily_par: Decimal | None = None
    tracks_daily: bool | None = None
    low_stock_threshold: Decimal | None = None
    category: str | None = Field(default=None, max_length=64)
    cost_per_unit: Decimal | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=512)


class StockAdjustBody(BaseModel):
    """purchase adds, wastage subtracts, opening sets absolute, adjustment is a signed delta."""

    reason: str = Field(pattern="^(purchase|wastage|opening|adjustment)$")
    quantity: Decimal
    notes: str | None = Field(default=None, max_length=512)


class InventoryTransactionResponse(BaseModel):
    id: UUID
    inventory_item_id: UUID
    delta: Decimal
    reason: str
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RecipeBomLine(BaseModel):
    inventory_item_id: UUID
    qty_per_serve: Decimal = Field(gt=0)


class ReplaceRecipeBomBody(BaseModel):
    lines: list[RecipeBomLine] = Field(default_factory=list)


class SetDailyStockBody(BaseModel):
    quantity: Decimal = Field(ge=0, description="How many units available for today (opening count)")


class BulkDailyStockItem(BaseModel):
    inventory_item_id: UUID
    quantity: Decimal = Field(ge=0)


class BulkDailyStockBody(BaseModel):
    items: list[BulkDailyStockItem] = Field(min_length=1)


class MenuInventoryLinkInput(BaseModel):
    inventory_item_id: UUID
    qty_per_serve: Decimal = Field(gt=0, default=Decimal("1"))


class TrackMenuStockBody(BaseModel):
    """Create or update daily stock tracking for a menu item (POS deducts on KOT)."""

    menu_item_id: UUID
    unit: str = Field(default="pcs", max_length=32)
    qty_per_kot: Decimal = Field(default=Decimal("1"), gt=0)
    today_quantity: Decimal = Field(ge=0, description="Opening count for today")


class LinkedMenuItem(BaseModel):
    menu_item_id: UUID
    menu_item_name: str
    qty_per_serve: Decimal


class InventoryItemResponse(BaseModel):
    id: UUID
    outlet_id: UUID
    name: str
    unit: str
    category: str
    tracks_daily: bool
    daily_par: Decimal | None
    stock_date: date | None
    today_opening: Decimal | None
    remaining_today: Decimal
    sold_today: Decimal
    current_stock: Decimal
    low_stock_threshold: Decimal | None
    cost_per_unit: Decimal | None
    notes: str | None
    linked_menu_items: list[LinkedMenuItem] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ItemQtyRow(BaseModel):
    menu_item_id: UUID | None = None
    item_name: str
    quantity: Decimal


class SalesByDateRow(BaseModel):
    date: date
    total_quantity: Decimal
    items: list[ItemQtyRow]


class SalesByWeekdayRow(BaseModel):
    weekday: str
    is_weekend: bool
    total_quantity: Decimal
    items: list[ItemQtyRow]


class SalesByMonthRow(BaseModel):
    month: str
    total_quantity: Decimal
    items: list[ItemQtyRow]


class SalesByYearRow(BaseModel):
    year: str
    total_quantity: Decimal
    items: list[ItemQtyRow]


class SalesByWeekRow(BaseModel):
    week: str
    week_start: date
    total_quantity: Decimal
    items: list[ItemQtyRow]


class SalesByQuarterRow(BaseModel):
    quarter: str
    year: int
    quarter_num: int
    total_quantity: Decimal
    items: list[ItemQtyRow]


class SalesWeekendSplit(BaseModel):
    weekday_total: Decimal
    weekend_total: Decimal
    weekday_items: list[ItemQtyRow]
    weekend_items: list[ItemQtyRow]


class SalesOverview(BaseModel):
    menu_items_in_catalog: int
    open_item_names: int
    order_lines_counted: int
    active_sale_days: int
    total_units_sold: Decimal
    weekday_units: Decimal
    weekend_units: Decimal


class ItemSalesSummaryRow(BaseModel):
    menu_item_id: UUID | None
    item_name: str
    total_quantity: Decimal
    by_weekday: list[ItemQtyRow]
    weekend_quantity: Decimal
    weekday_quantity: Decimal


class InventorySalesAnalyticsResponse(BaseModel):
    from_date: date
    to_date: date
    overview: SalesOverview
    by_day: list[SalesByDateRow]
    by_weekday: list[SalesByWeekdayRow]
    by_week: list[SalesByWeekRow]
    by_month: list[SalesByMonthRow]
    by_quarter: list[SalesByQuarterRow]
    by_year: list[SalesByYearRow]
    weekend_split: SalesWeekendSplit
    by_item: list[ItemSalesSummaryRow]
    top_items: list[ItemSalesSummaryRow]
