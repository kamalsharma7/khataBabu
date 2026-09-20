from __future__ import annotations

import enum
import uuid
from datetime import time
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String, Time, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.tenant import Outlet


class ResourceKind(str, enum.Enum):
    DINE_TABLE = "dine_table"
    TIME_BASED = "time_based"


class AreaBillingMode(str, enum.Enum):
    DINE_IN = "dine_in"
    TIME_BASED = "time_based"


class VenueArea(Base, TimestampMixin):
    """Partition / section (AC hall, Snooker, Garden, Private rooms, etc.)."""

    __tablename__ = "venue_areas"
    __table_args__ = (
        UniqueConstraint("outlet_id", "name", name="uq_venue_areas_outlet_name"),
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
    billing_mode: Mapped[AreaBillingMode] = mapped_column(
        Enum(
            AreaBillingMode,
            name="area_billing_mode",
            native_enum=False,
            values_callable=lambda choices: [c.value for c in choices],
        ),
        nullable=False,
        default=AreaBillingMode.DINE_IN,
    )
    operating_start: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    operating_end: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    hourly_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    outlet: Mapped["Outlet"] = relationship(back_populates="areas")
    tables: Mapped[list["VenueTable"]] = relationship(
        back_populates="area",
        cascade="all, delete-orphan",
    )


class VenueTable(Base, TimestampMixin):
    __tablename__ = "venue_tables"
    __table_args__ = (
        UniqueConstraint("area_id", "label", name="uq_venue_tables_area_label"),
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
    area_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("venue_areas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resource_kind: Mapped[ResourceKind] = mapped_column(
        Enum(
            ResourceKind,
            name="resource_kind",
            native_enum=False,
            values_callable=lambda choices: [c.value for c in choices],
        ),
        nullable=False,
        default=ResourceKind.DINE_TABLE,
    )
    hourly_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    area: Mapped["VenueArea"] = relationship(back_populates="tables")
    outlet: Mapped["Outlet"] = relationship(back_populates="venue_tables")
    pos_orders: Mapped[list["PosOrder"]] = relationship(
        "PosOrder",
        back_populates="venue_table",
    )
