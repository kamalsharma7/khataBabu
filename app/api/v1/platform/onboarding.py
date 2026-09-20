from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.platform import get_current_platform_admin
from app.db.deps import get_db
from app.models.platform_admin import PlatformAdmin
from app.schemas.platform.onboarding import (
    TenantOnboardingCreateRequest,
    TenantOnboardingCreateResponse,
    TenantStatusUpdateRequest,
    TenantSummary,
)
from app.services.platform.onboarding_service import PlatformOnboardingService

router = APIRouter()


@router.post("/tenants", response_model=TenantOnboardingCreateResponse, status_code=201)
async def create_tenant(
    body: TenantOnboardingCreateRequest,
    db: AsyncSession = Depends(get_db),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> TenantOnboardingCreateResponse:
    service = PlatformOnboardingService(db)
    return await service.create_tenant(body, admin)


@router.get("/tenants", response_model=list[TenantSummary])
async def list_tenants(
    db: AsyncSession = Depends(get_db),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> list[TenantSummary]:
    service = PlatformOnboardingService(db)
    return await service.list_tenants()


@router.patch("/tenants/{business_id}/status", response_model=TenantSummary)
async def update_tenant_status(
    business_id: uuid.UUID,
    body: TenantStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> TenantSummary:
    service = PlatformOnboardingService(db)
    return await service.update_tenant_status(business_id, body, admin)
