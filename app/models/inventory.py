from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from datetime import datetime

from datetime import date

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.menu import MenuItem
    from app.models.tenant import Outlet


class InventoryItem(Base, TimestampMixin):
    __tablename__ = "inventory_items"
    __table_args__ = (
        UniqueConstraint("outlet_id", "name", name="uq_inventory_items_outlet_name"),
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
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False, default="pcs")
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="grocery")
    current_stock: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    low_stock_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)
    cost_per_unit: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    tracks_daily: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    daily_par: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)
    stock_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    today_opening: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)

    outlet: Mapped["Outlet"] = relationship(back_populates="inventory_items")
    menu_links: Mapped[list["MenuItemInventoryLink"]] = relationship(
        back_populates="inventory_item",
        cascade="all, delete-orphan",
    )


class MenuItemInventoryLink(Base, TimestampMixin):
    __tablename__ = "menu_item_inventory_links"
    __table_args__ = (
        UniqueConstraint("menu_item_id", "inventory_item_id", name="uq_menu_item_inventory"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    menu_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("menu_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    qty_per_serve: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=1)

    inventory_item: Mapped["InventoryItem"] = relationship(back_populates="menu_links")
    menu_item: Mapped["MenuItem"] = relationship(back_populates="inventory_links")


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    outlet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("outlets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    delta: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    order_line_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pos_order_lines.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
