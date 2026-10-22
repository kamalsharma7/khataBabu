from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.platform import get_current_platform_admin
from app.db.deps import get_db
from app.models.platform_admin import PlatformAdmin
from app.schemas.platform.territory import (
    TerritoryAnalyticsResponse,
    TerritoryRevenueAnalyticsResponse,
)
from app.services.platform.territory_service import PlatformTerritoryService

router = APIRouter()


@router.get("/analytics", response_model=TerritoryAnalyticsResponse)
async def territory_analytics(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> TerritoryAnalyticsResponse:
    service = PlatformTerritoryService(db)
    return await service.analytics(from_date, to_date)


@router.get("/revenue/analytics", response_model=TerritoryRevenueAnalyticsResponse)
async def territory_revenue_analytics(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> TerritoryRevenueAnalyticsResponse:
    service = PlatformTerritoryService(db)
    return await service.revenue_analytics(from_date, to_date)
