from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class PurchaseInvoice(Base, TimestampMixin):
    """A vendor bill: what the owner bought for the kitchen (paneer 400 g, oil 5 L...)."""

    __tablename__ = "purchase_invoices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    outlet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("outlets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vendor_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    vendor_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    vendor_gstin: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    invoice_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    po_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    subtotal_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    tax_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    discount_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    other_charges_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    paid_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    payment_mode: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    payment_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unpaid")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="saved")
    stock_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("business_owners.id", ondelete="SET NULL"),
        nullable=True,
    )

    lines: Mapped[list["PurchaseInvoiceLine"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="PurchaseInvoiceLine.sort_order",
    )
    payments: Mapped[list["PurchasePayment"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="PurchasePayment.paid_on",
    )


class PurchaseInvoiceLine(Base):
    __tablename__ = "purchase_invoice_lines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    inventory_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    unit_price_inr: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    tax_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    line_total_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    invoice: Mapped["PurchaseInvoice"] = relationship(back_populates="lines")


class PurchasePayment(Base):
    __tablename__ = "purchase_payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    payment_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="cash")
    paid_on: Mapped[date] = mapped_column(Date, nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("business_owners.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    invoice: Mapped["PurchaseInvoice"] = relationship(back_populates="payments")
