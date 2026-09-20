from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import JSON, Boolean, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    BusinessType,
    OperatingModel,
    OwnerRole,
    PlanTier,
    TenantStatus,
    VenueKind,
)
from app.models.mixins import TimestampMixin


class Business(Base, TimestampMixin):
    __tablename__ = "businesses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_type: Mapped[BusinessType] = mapped_column(
        Enum(BusinessType, name="business_type", native_enum=False),
        nullable=False,
    )
    primary_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    primary_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    city: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str] = mapped_column(String(128), nullable=False)
    gst_registered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gstin: Mapped[Optional[str]] = mapped_column(String(15), nullable=True)
    fssai: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    pan: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    plan_tier: Mapped[PlanTier] = mapped_column(
        Enum(PlanTier, name="plan_tier", native_enum=False),
        nullable=False,
        default=PlanTier.BASIC,
    )
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, name="tenant_status", native_enum=False),
        nullable=False,
        default=TenantStatus.DRAFT,
    )
    internal_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    onboarded_by_admin_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("platform_admins.id", ondelete="SET NULL"),
        nullable=True,
    )
    analytics_pin_hash: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    outlets: Mapped[list["Outlet"]] = relationship(back_populates="business", cascade="all, delete-orphan")
    owners: Mapped[list["BusinessOwner"]] = relationship(
        back_populates="business",
        cascade="all, delete-orphan",
    )


class Outlet(Base, TimestampMixin):
    __tablename__ = "outlets"
    __table_args__ = (UniqueConstraint("ref_code", name="uq_outlets_ref_code"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line: Mapped[str] = mapped_column(String(512), nullable=False)
    pincode: Mapped[str] = mapped_column(String(12), nullable=False)
    outlet_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    operating_models: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    venue_kinds: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    time_based_billing_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rough_scale_notes: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    ref_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, name="outlet_status", native_enum=False),
        nullable=False,
        default=TenantStatus.DRAFT,
    )

    business: Mapped["Business"] = relationship(back_populates="outlets")
    areas: Mapped[list["VenueArea"]] = relationship(
        "VenueArea",
        back_populates="outlet",
        cascade="all, delete-orphan",
    )
    venue_tables: Mapped[list["VenueTable"]] = relationship(
        "VenueTable",
        back_populates="outlet",
        cascade="all, delete-orphan",
    )
    menu_categories: Mapped[list["MenuCategory"]] = relationship(
        "MenuCategory",
        back_populates="outlet",
        cascade="all, delete-orphan",
    )
    menu_items: Mapped[list["MenuItem"]] = relationship(
        "MenuItem",
        back_populates="outlet",
        cascade="all, delete-orphan",
    )
    pos_orders: Mapped[list["PosOrder"]] = relationship(
        "PosOrder",
        back_populates="outlet",
        cascade="all, delete-orphan",
    )


class BusinessOwner(Base, TimestampMixin):
    """First login identity for the customer — separate from platform_admins."""

    __tablename__ = "business_owners"
    __table_args__ = (
        UniqueConstraint("username", name="uq_business_owners_username"),
        UniqueConstraint("email", name="uq_business_owners_email"),
        UniqueConstraint("mobile", name="uq_business_owners_mobile"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    mobile: Mapped[str] = mapped_column(String(20), nullable=False)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    role: Mapped[OwnerRole] = mapped_column(
        Enum(OwnerRole, name="owner_role", native_enum=False),
        nullable=False,
        default=OwnerRole.OWNER,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    business: Mapped["Business"] = relationship(back_populates="owners")
