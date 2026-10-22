from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compliance import TenantAuditLog
from app.models.tenant import BusinessOwner
from app.schemas.owner.settings import AuditLogEntryResponse, AuditLogListResponse
from app.services.owner.permissions import PERM_AUDIT_VIEW, has_permission


class ComplianceQueryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_audit(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID | None,
        limit: int = 100,
    ) -> AuditLogListResponse:
        if not has_permission(owner.role, PERM_AUDIT_VIEW):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access")
        q = (
            select(TenantAuditLog)
            .where(TenantAuditLog.business_id == owner.business_id)
            .order_by(TenantAuditLog.created_at.desc())
            .limit(min(limit, 200))
        )
        if outlet_id is not None:
            q = q.where(TenantAuditLog.outlet_id == outlet_id)
        result = await self.db.execute(q)
        items = [
            AuditLogEntryResponse(
                id=str(row.id),
                outlet_id=str(row.outlet_id) if row.outlet_id else None,
                actor_username=row.actor_username,
                action=row.action,
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                summary=row.summary,
                reason=row.reason,
                created_at=row.created_at.isoformat(),
            )
            for row in result.scalars().all()
        ]
        return AuditLogListResponse(items=items)
