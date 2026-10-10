from __future__ import annotations

import uuid

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


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
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
