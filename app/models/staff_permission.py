from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class StaffPermissionGrant(Base, TimestampMixin):
    """Per-outlet permission tick for a receptionist / worker login."""

    __tablename__ = "staff_permission_grants"
    __table_args__ = (
        UniqueConstraint("outlet_id", "owner_id", "permission", name="uq_staff_perm_outlet_owner_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    outlet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("outlets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("business_owners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission: Mapped[str] = mapped_column(String(64), nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by_owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("business_owners.id", ondelete="SET NULL"),
        nullable=True,
    )
