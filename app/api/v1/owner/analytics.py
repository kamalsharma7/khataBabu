from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.analytics import require_analytics_unlock
from app.api.deps.owner import get_current_owner
from app.core.config import Settings, get_settings
from app.db.deps import get_db
from app.models.tenant import BusinessOwner
from app.schemas.owner.analytics import (
    AnalyticsOrdersResponse,
    AnalyticsStatusResponse,
    AnalyticsSummaryResponse,
    AnalyticsUnlockRequest,
    AnalyticsUnlockResponse,
)
from app.services.owner.analytics_service import OwnerAnalyticsService

router = APIRouter(prefix="/outlets/{outlet_id}/analytics", tags=["owner-analytics"])


@router.get("/status", response_model=AnalyticsStatusResponse)
async def analytics_status(
    outlet_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AnalyticsStatusResponse:
    service = OwnerAnalyticsService(db, settings)
    return await service.status(owner, outlet_id)


@router.post("/unlock", response_model=AnalyticsUnlockResponse)
async def analytics_unlock(
    outlet_id: uuid.UUID,
    body: AnalyticsUnlockRequest,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AnalyticsUnlockResponse:
    service = OwnerAnalyticsService(db, settings)
    return await service.unlock(
        owner,
        outlet_id,
        pin=body.pin,
        login_password=body.login_password,
        new_pin=body.new_pin,
    )


@router.get("/summary", response_model=AnalyticsSummaryResponse)
async def analytics_summary(
    outlet_id: uuid.UUID,
    from_datetime: datetime = Query(..., description="Range start (ISO 8601, with timezone)"),
    to_datetime: datetime = Query(..., description="Range end (ISO 8601, with timezone)"),
    owner: BusinessOwner = Depends(require_analytics_unlock),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AnalyticsSummaryResponse:
    service = OwnerAnalyticsService(db, settings)
    return await service.summary(owner, outlet_id, from_datetime, to_datetime)


@router.get("/orders", response_model=AnalyticsOrdersResponse)
async def analytics_orders(
    outlet_id: uuid.UUID,
    from_datetime: datetime = Query(...),
    to_datetime: datetime = Query(...),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    owner: BusinessOwner = Depends(require_analytics_unlock),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AnalyticsOrdersResponse:
    service = OwnerAnalyticsService(db, settings)
    return await service.list_orders(
        owner,
        outlet_id,
        from_datetime,
        to_datetime,
        offset,
        limit,
    )
