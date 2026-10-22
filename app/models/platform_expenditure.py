from __future__ import annotations

import uuid
from typing import Optional
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import PlatformExpenditureCategory
from app.models.mixins import TimestampMixin

_ENUM_VALUES = lambda enum_cls: [member.value for member in enum_cls]


class PlatformExpenditure(Base, TimestampMixin):
    """KhataBabu internal business spend (platform console only)."""

    __tablename__ = "platform_expenditures"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    category: Mapped[PlatformExpenditureCategory] = mapped_column(
        Enum(
            PlatformExpenditureCategory,
            name="platform_expenditure_category",
            native_enum=False,
            values_callable=_ENUM_VALUES,
        ),
        nullable=False,
        index=True,
    )
    amount_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    spent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    recorded_by_admin_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("platform_admins.id", ondelete="SET NULL"),
        nullable=True,
    )
    sales_employee_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("platform_sales_employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
