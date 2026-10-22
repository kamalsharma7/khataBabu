from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compliance import TenantAuditLog
from app.models.tenant import BusinessOwner


class TenantAuditService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def log(
        self,
        *,
        business_id: uuid.UUID,
        outlet_id: uuid.UUID | None,
        actor: BusinessOwner | None,
        action: str,
        entity_type: str,
        entity_id: str | None,
        summary: str,
        detail: dict[str, Any] | None = None,
        reason: str | None = None,
    ) -> None:
        row = TenantAuditLog(
            business_id=business_id,
            outlet_id=outlet_id,
            actor_owner_id=actor.id if actor else None,
            actor_username=actor.username if actor else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary,
            detail=detail,
            reason=reason,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(row)
