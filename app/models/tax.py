from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class OutletTaxProfileItem(Base):
    __tablename__ = "outlet_tax_profile_items"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("outlet_tax_profiles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    menu_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("menu_items.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )


class OutletTaxProfile(Base, TimestampMixin):
    """Venue tax rule — GST / VAT / other. GSTIN does not turn this on."""

    __tablename__ = "outlet_tax_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    outlet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("outlets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    scheme: Mapped[str] = mapped_column(String(16), nullable=False, default="gst")
    gst_slab: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    rate_percent: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=Decimal("0"))
    cgst_percent: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=Decimal("0"))
    sgst_percent: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=Decimal("0"))
    igst_percent: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=Decimal("0"))
    title: Mapped[str] = mapped_column(String(64), nullable=False, default="GST")
    cgst_title: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sgst_title: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    igst_title: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    title_suffix: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    method: Mapped[str] = mapped_column(String(16), nullable=False, default="forward")
    applies_dine_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    applies_takeaway: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    applies_delivery: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="venue")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    items: Mapped[list[OutletTaxProfileItem]] = relationship(
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def menu_item_ids(self) -> list[uuid.UUID]:
        return [row.menu_item_id for row in self.items]
