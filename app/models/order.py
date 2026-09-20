from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    BillStatus,
    FoodType,
    KotStatus,
    OrderLineStatus,
    OrderStatus,
    OrderType,
    PaymentMethod,
)
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.tenant import BusinessOwner, Outlet
    from app.models.venue import VenueTable


class OutletCounter(Base):
    """Daily sequence for order / KOT / bill numbers per outlet."""

    __tablename__ = "outlet_counters"
    __table_args__ = (
        UniqueConstraint(
            "outlet_id",
            "counter_date",
            "counter_kind",
            name="uq_outlet_counters_outlet_date_kind",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    outlet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("outlets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    counter_date: Mapped[date] = mapped_column(Date, nullable=False)
    counter_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PosOrder(Base, TimestampMixin):
    __tablename__ = "pos_orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    outlet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("outlets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_type: Mapped[OrderType] = mapped_column(
        Enum(OrderType, name="order_type", native_enum=False),
        nullable=False,
        default=OrderType.DINE_IN,
    )
    order_number: Mapped[int] = mapped_column(Integer, nullable=False)
    venue_table_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("venue_tables.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    table_label_snapshot: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status", native_enum=False),
        nullable=False,
        default=OrderStatus.OPEN,
    )
    guest_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    customer_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    customer_mobile: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    pay_later: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    opened_by_owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("business_owners.id", ondelete="SET NULL"),
        nullable=True,
    )
    settled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    time_session_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    time_session_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    time_billed_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hourly_rate_snapshot: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    time_charge: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    outlet: Mapped["Outlet"] = relationship(back_populates="pos_orders")
    venue_table: Mapped[Optional["VenueTable"]] = relationship(back_populates="pos_orders")
    lines: Mapped[list["PosOrderLine"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="PosOrderLine.created_at",
    )
    kots: Mapped[list["PosKot"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    bills: Mapped[list["PosBill"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class PosOrderLine(Base, TimestampMixin):
    __tablename__ = "pos_order_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pos_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    menu_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("menu_items.id", ondelete="RESTRICT"),
        nullable=True,
    )
    is_open_item: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    menu_item_variation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("menu_item_variations.id", ondelete="SET NULL"),
        nullable=True,
    )
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    variation_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    addons_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    line_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    food_type: Mapped[FoodType] = mapped_column(
        Enum(
            FoodType,
            name="food_type_line",
            native_enum=False,
            values_callable=lambda choices: [c.value for c in choices],
        ),
        nullable=False,
        default=FoodType.VEG,
    )
    status: Mapped[OrderLineStatus] = mapped_column(
        Enum(OrderLineStatus, name="order_line_status", native_enum=False),
        nullable=False,
        default=OrderLineStatus.PENDING_KOT,
    )

    order: Mapped["PosOrder"] = relationship(back_populates="lines")
    addons: Mapped[list["PosOrderLineAddon"]] = relationship(
        back_populates="order_line",
        cascade="all, delete-orphan",
    )
    kot_lines: Mapped[list["PosKotLine"]] = relationship(back_populates="order_line")


class PosOrderLineAddon(Base, TimestampMixin):
    __tablename__ = "pos_order_line_addons"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    order_line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pos_order_lines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    menu_item_addon_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("menu_item_addons.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    order_line: Mapped["PosOrderLine"] = relationship(back_populates="addons")


class PosKot(Base, TimestampMixin):
    __tablename__ = "pos_kots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    outlet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("outlets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pos_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kot_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[KotStatus] = mapped_column(
        Enum(KotStatus, name="kot_status", native_enum=False),
        nullable=False,
        default=KotStatus.ACTIVE,
    )
    notes: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    order: Mapped["PosOrder"] = relationship(back_populates="kots")
    lines: Mapped[list["PosKotLine"]] = relationship(
        back_populates="kot",
        cascade="all, delete-orphan",
    )


class PosKotLine(Base, TimestampMixin):
    __tablename__ = "pos_kot_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    kot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pos_kots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pos_order_lines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    kot: Mapped["PosKot"] = relationship(back_populates="lines")
    order_line: Mapped["PosOrderLine"] = relationship(back_populates="kot_lines")


class PosBill(Base, TimestampMixin):
    __tablename__ = "pos_bills"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    outlet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("outlets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pos_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bill_number: Mapped[int] = mapped_column(Integer, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    tax_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    round_off: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[BillStatus] = mapped_column(
        Enum(BillStatus, name="bill_status", native_enum=False),
        nullable=False,
        default=BillStatus.OPEN,
    )

    order: Mapped["PosOrder"] = relationship(back_populates="bills")
    payments: Mapped[list["PosBillPayment"]] = relationship(
        back_populates="bill",
        cascade="all, delete-orphan",
    )


class PosBillPayment(Base, TimestampMixin):
    __tablename__ = "pos_bill_payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    bill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pos_bills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method", native_enum=False),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    bill: Mapped["PosBill"] = relationship(back_populates="payments")
