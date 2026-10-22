from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

PAYMENT_MODE_PATTERN = "^(cash|upi|card|bank|credit|other)$"


class PurchaseLineInput(BaseModel):
    inventory_item_id: UUID | None = None
    item_name: str = Field(min_length=1, max_length=255)
    quantity: Decimal = Field(gt=0)
    unit: str = Field(default="pcs", max_length=32)
    unit_price_inr: Decimal = Field(default=Decimal("0"), ge=0)
    tax_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class PurchaseInvoiceCreate(BaseModel):
    vendor_name: str = Field(min_length=1, max_length=255)
    vendor_phone: str | None = Field(default=None, max_length=20)
    vendor_gstin: str | None = Field(default=None, max_length=20)
    invoice_number: str | None = Field(default=None, max_length=64)
    invoice_date: date
    po_reference: str | None = Field(default=None, max_length=64)
    discount_inr: Decimal = Field(default=Decimal("0"), ge=0)
    other_charges_inr: Decimal = Field(default=Decimal("0"), ge=0)
    paid_inr: Decimal = Field(default=Decimal("0"), ge=0)
    payment_mode: str | None = Field(default=None, pattern=PAYMENT_MODE_PATTERN)
    notes: str | None = Field(default=None, max_length=2000)
    apply_stock: bool = Field(default=True, description="Add purchased qty to linked raw materials")
    lines: list[PurchaseLineInput] = Field(min_length=1)


class PurchaseInvoiceUpdate(BaseModel):
    """Header-only edits; lines are locked once stock has been applied."""

    vendor_name: str | None = Field(default=None, max_length=255)
    vendor_phone: str | None = Field(default=None, max_length=20)
    vendor_gstin: str | None = Field(default=None, max_length=20)
    invoice_number: str | None = Field(default=None, max_length=64)
    invoice_date: date | None = None
    po_reference: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=2000)


class PurchasePaymentCreate(BaseModel):
    amount_inr: Decimal = Field(gt=0)
    payment_mode: str = Field(default="cash", pattern=PAYMENT_MODE_PATTERN)
    paid_on: date | None = None
    reference: str | None = Field(default=None, max_length=128)
    notes: str | None = Field(default=None, max_length=1000)


class PurchaseLineResponse(BaseModel):
    id: UUID
    inventory_item_id: UUID | None
    item_name: str
    quantity: Decimal
    unit: str
    unit_price_inr: Decimal
    tax_percent: Decimal
    line_total_inr: Decimal

    model_config = {"from_attributes": True}


class PurchasePaymentResponse(BaseModel):
    id: UUID
    amount_inr: Decimal
    payment_mode: str
    paid_on: date
    reference: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PurchaseInvoiceSummary(BaseModel):
    id: UUID
    vendor_name: str
    invoice_number: str | None
    invoice_date: date
    po_reference: str | None
    total_inr: Decimal
    paid_inr: Decimal
    balance_inr: Decimal
    tax_inr: Decimal
    payment_status: str
    status: str
    stock_applied: bool
    line_count: int
    created_by_name: str | None
    created_at: datetime


class PurchaseInvoiceDetail(PurchaseInvoiceSummary):
    outlet_id: UUID
    vendor_phone: str | None
    vendor_gstin: str | None
    subtotal_inr: Decimal
    discount_inr: Decimal
    other_charges_inr: Decimal
    payment_mode: str | None
    notes: str | None
    lines: list[PurchaseLineResponse]
    payments: list[PurchasePaymentResponse]


class PurchaseListTotals(BaseModel):
    invoice_count: int
    total_inr: Decimal
    paid_inr: Decimal
    outstanding_inr: Decimal
    tax_inr: Decimal


class PurchaseListResponse(BaseModel):
    from_date: date | None
    to_date: date | None
    totals: PurchaseListTotals
    vendors: list[str]
    invoices: list[PurchaseInvoiceSummary]
