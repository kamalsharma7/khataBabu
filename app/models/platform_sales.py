from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Enum, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import (
    SalesBehaviorStatus,
    SalesEmploymentStatus,
    SalesProfessionalStatus,
)
from app.models.mixins import TimestampMixin

_ENUM_VALUES = lambda enum_cls: [member.value for member in enum_cls]


class PlatformSalesEmployee(Base, TimestampMixin):
    """KhataBabu sales / client-success staff assigned to onboarded venues."""

    __tablename__ = "platform_sales_employees"
    __table_args__ = (
        UniqueConstraint("employee_code", name="uq_platform_sales_employees_code"),
        UniqueConstraint("mobile", name="uq_platform_sales_employees_mobile"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    employee_code: Mapped[str] = mapped_column(String(32), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mobile: Mapped[str] = mapped_column(String(20), nullable=False)
    aadhaar_number: Mapped[str] = mapped_column(String(12), nullable=False)
    pan_number: Mapped[str] = mapped_column(String(10), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    date_of_joining: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    employment_status: Mapped[SalesEmploymentStatus] = mapped_column(
        Enum(
            SalesEmploymentStatus,
            name="sales_employment_status",
            native_enum=False,
            values_callable=_ENUM_VALUES,
        ),
        nullable=False,
        default=SalesEmploymentStatus.ACTIVE,
    )
    behavior_status: Mapped[SalesBehaviorStatus] = mapped_column(
        Enum(
            SalesBehaviorStatus,
            name="sales_behavior_status",
            native_enum=False,
            values_callable=_ENUM_VALUES,
        ),
        nullable=False,
        default=SalesBehaviorStatus.GOOD,
    )
    professional_status: Mapped[SalesProfessionalStatus] = mapped_column(
        Enum(
            SalesProfessionalStatus,
            name="sales_professional_status",
            native_enum=False,
            values_callable=_ENUM_VALUES,
        ),
        nullable=False,
        default=SalesProfessionalStatus.GOOD,
    )
