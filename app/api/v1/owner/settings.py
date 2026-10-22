from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.owner import get_current_owner
from app.api.deps.permissions import require_permission
from app.db.deps import get_db
from app.models.tenant import BusinessOwner
from app.schemas.owner.settings import (
    BusinessProfileUpdate,
    BusinessSettingsResponse,
    ManagerPinUpdate,
    PosPolicyUpdate,
)
from app.services.owner.business_settings_service import BusinessSettingsService
from app.services.owner.permissions import PERM_SETTINGS_ALL, PERM_SETTINGS_VIEW

router = APIRouter(prefix="/business", tags=["owner-settings"])


@router.get("/settings", response_model=BusinessSettingsResponse)
async def get_business_settings(
    owner: BusinessOwner = Depends(require_permission(PERM_SETTINGS_VIEW)),
    db: AsyncSession = Depends(get_db),
) -> BusinessSettingsResponse:
    return await BusinessSettingsService(db).get_settings(owner)


@router.patch("/settings/profile", response_model=BusinessSettingsResponse)
async def update_business_profile(
    body: BusinessProfileUpdate,
    owner: BusinessOwner = Depends(require_permission(PERM_SETTINGS_ALL)),
    db: AsyncSession = Depends(get_db),
) -> BusinessSettingsResponse:
    return await BusinessSettingsService(db).update_profile(owner, body)


@router.patch("/settings/policy", response_model=BusinessSettingsResponse)
async def update_pos_policy(
    body: PosPolicyUpdate,
    owner: BusinessOwner = Depends(require_permission(PERM_SETTINGS_ALL)),
    db: AsyncSession = Depends(get_db),
) -> BusinessSettingsResponse:
    return await BusinessSettingsService(db).update_policy(owner, body)


@router.post("/settings/manager-pin", response_model=BusinessSettingsResponse)
async def set_manager_pin(
    body: ManagerPinUpdate,
    owner: BusinessOwner = Depends(require_permission(PERM_SETTINGS_ALL)),
    db: AsyncSession = Depends(get_db),
) -> BusinessSettingsResponse:
    return await BusinessSettingsService(db).set_manager_pin(owner, body)
