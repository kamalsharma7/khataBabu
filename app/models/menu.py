from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import FoodType
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.tenant import Outlet


class MenuCategory(Base, TimestampMixin):
    __tablename__ = "menu_categories"
    __table_args__ = (
        UniqueConstraint("outlet_id", "name", name="uq_menu_categories_outlet_name"),
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
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    outlet: Mapped["Outlet"] = relationship(back_populates="menu_categories")
    items: Mapped[list["MenuItem"]] = relationship(
        back_populates="category",
        cascade="all, delete-orphan",
    )


class MenuItem(Base, TimestampMixin):
    __tablename__ = "menu_items"

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
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("menu_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    short_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    is_veg: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    food_type: Mapped[FoodType] = mapped_column(
        Enum(
            FoodType,
            name="food_type",
            native_enum=False,
            values_callable=lambda choices: [c.value for c in choices],
        ),
        nullable=False,
        default=FoodType.VEG,
    )
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    gst_applicable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cgst_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    sgst_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)

    category: Mapped["MenuCategory"] = relationship(back_populates="items")
    outlet: Mapped["Outlet"] = relationship(back_populates="menu_items")
    variations: Mapped[list["MenuItemVariation"]] = relationship(
        back_populates="menu_item",
        cascade="all, delete-orphan",
        order_by="MenuItemVariation.sort_order",
    )
    addons: Mapped[list["MenuItemAddon"]] = relationship(
        back_populates="menu_item",
        cascade="all, delete-orphan",
        order_by="MenuItemAddon.sort_order",
    )
    addon_groups: Mapped[list["MenuAddonGroup"]] = relationship(
        back_populates="menu_item",
        cascade="all, delete-orphan",
        order_by="MenuAddonGroup.sort_order",
    )
    inventory_links: Mapped[list["MenuItemInventoryLink"]] = relationship(
        "MenuItemInventoryLink",
        back_populates="menu_item",
        cascade="all, delete-orphan",
    )


class MenuItemVariation(Base, TimestampMixin):
    """Size / style options (Small, Medium, Large) — each with its own price."""

    __tablename__ = "menu_item_variations"

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
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    weight_grams: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    food_type: Mapped[Optional[FoodType]] = mapped_column(
        Enum(
            FoodType,
            name="food_type",
            native_enum=False,
            values_callable=lambda choices: [c.value for c in choices],
        ),
        nullable=True,
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("menu_item_variations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    menu_item: Mapped["MenuItem"] = relationship(back_populates="variations")
    parent: Mapped[Optional["MenuItemVariation"]] = relationship(
        remote_side="MenuItemVariation.id",
        back_populates="children",
    )
    children: Mapped[list["MenuItemVariation"]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
    )


class MenuAddonGroup(Base, TimestampMixin):
    """Sauces / extras — min/max how many the cashier must pick."""

    __tablename__ = "menu_addon_groups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    menu_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("menu_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    min_select: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_select: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    menu_item: Mapped["MenuItem"] = relationship(back_populates="addon_groups")
    addons: Mapped[list["MenuItemAddon"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="MenuItemAddon.sort_order",
    )


class MenuItemAddon(Base, TimestampMixin):
    """Optional toppings / add-ons (extra cheese, olives, etc.)."""

    __tablename__ = "menu_item_addons"

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
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    weight_grams: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    food_type: Mapped[Optional[FoodType]] = mapped_column(
        Enum(
            FoodType,
            name="food_type",
            native_enum=False,
            values_callable=lambda choices: [c.value for c in choices],
        ),
        nullable=True,
    )
    group_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("menu_addon_groups.id", ondelete="SET NULL"),
        nullable=True,
    )

    menu_item: Mapped["MenuItem"] = relationship(back_populates="addons")
    group: Mapped[Optional["MenuAddonGroup"]] = relationship(back_populates="addons")
