from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import OrderType

SCHEME_PATTERN = "^(gst|vat|other)$"
SLAB_PATTERN = "^(gst_5|gst_18|gst_40|igst|custom)$"
METHOD_PATTERN = "^(forward|backward|tax_on_tax)$"


class TaxProfileBase(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    scheme: str = Field(default="gst", pattern=SCHEME_PATTERN)
    gst_slab: Optional[str] = Field(default="gst_5", pattern=SLAB_PATTERN)
    rate_percent: Decimal = Field(default=Decimal("5"), ge=0, le=100)
    cgst_percent: Decimal = Field(default=Decimal("2.5"), ge=0, le=100)
    sgst_percent: Decimal = Field(default=Decimal("2.5"), ge=0, le=100)
    igst_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    title: str = Field(default="", max_length=64)
    cgst_title: Optional[str] = Field(default=None, max_length=64)
    sgst_title: Optional[str] = Field(default=None, max_length=64)
    igst_title: Optional[str] = Field(default=None, max_length=64)
    title_suffix: Optional[str] = Field(default=None, max_length=32)
    method: str = Field(default="forward", pattern=METHOD_PATTERN)
    applies_dine_in: bool = True
    applies_takeaway: bool = True
    applies_delivery: bool = True
    is_active: bool = True
    scope: str = Field(default="venue", pattern="^(venue|items)$")
    menu_item_ids: list[UUID] = Field(default_factory=list)
    notes: Optional[str] = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def at_least_one_order_type(self) -> "TaxProfileBase":
        if not (self.applies_dine_in or self.applies_takeaway or self.applies_delivery):
            raise ValueError("Pick at least one order type (dine-in, takeaway or delivery)")
        if self.scheme != "gst" and not self.menu_item_ids:
            raise ValueError("VAT / other tax applies to selected menu items — pick at least one dish")
        return self


class TaxProfileCreate(TaxProfileBase):
    pass


class TaxProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128)
    scheme: Optional[str] = Field(default=None, pattern=SCHEME_PATTERN)
    gst_slab: Optional[str] = Field(default=None, pattern=SLAB_PATTERN)
    rate_percent: Optional[Decimal] = Field(default=None, ge=0, le=100)
    cgst_percent: Optional[Decimal] = Field(default=None, ge=0, le=100)
    sgst_percent: Optional[Decimal] = Field(default=None, ge=0, le=100)
    igst_percent: Optional[Decimal] = Field(default=None, ge=0, le=100)
    title: Optional[str] = Field(default=None, max_length=64)
    cgst_title: Optional[str] = Field(default=None, max_length=64)
    sgst_title: Optional[str] = Field(default=None, max_length=64)
    igst_title: Optional[str] = Field(default=None, max_length=64)
    title_suffix: Optional[str] = Field(default=None, max_length=32)
    method: Optional[str] = Field(default=None, pattern=METHOD_PATTERN)
    applies_dine_in: Optional[bool] = None
    applies_takeaway: Optional[bool] = None
    applies_delivery: Optional[bool] = None
    is_active: Optional[bool] = None
    scope: Optional[str] = Field(default=None, pattern="^(venue|items)$")
    menu_item_ids: Optional[list[UUID]] = None
    notes: Optional[str] = Field(default=None, max_length=255)


class TaxProfileResponse(TaxProfileBase):
    id: UUID
    outlet_id: UUID
    sort_order: int = 0

    model_config = {"from_attributes": True}


class TaxPreviewRequest(BaseModel):
    amount_inr: Decimal = Field(default=Decimal("100"), gt=0)
    order_type: OrderType = OrderType.DINE_IN
    apply_tax: bool = True


class TaxPreviewLine(BaseModel):
    title: str
    amount_inr: Decimal


class TaxPreviewResponse(BaseModel):
    amount_inr: Decimal
    method: str
    tax_label: Optional[str] = None
    tax_percent: Decimal
    tax_amount: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    guest_pays: Decimal
    lines: list[TaxPreviewLine] = Field(default_factory=list)
    applied: bool
    note: str


class TaxCatalogResponse(BaseModel):
    profiles: list[TaxProfileResponse]
    tax_enabled: bool
    default_tax_percent: Decimal
    default_method: str
    tax_label: Optional[str] = None
