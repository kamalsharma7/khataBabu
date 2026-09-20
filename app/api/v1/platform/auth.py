from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.platform import get_current_platform_admin
from app.core.config import Settings, get_settings
from app.db.deps import get_db
from app.models.platform_admin import PlatformAdmin
from app.schemas.platform.auth import (
    PlatformAdminProfile,
    PlatformLoginRequest,
    PlatformTokenResponse,
)
from app.services.platform.auth_service import PlatformAuthService

router = APIRouter()


@router.post("/login", response_model=PlatformTokenResponse)
async def platform_login(
    body: PlatformLoginRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PlatformTokenResponse:
    """Password-only login until SMS OTP is integrated."""
    service = PlatformAuthService(db, settings)
    return await service.login(body.username, body.password)


@router.get("/me", response_model=PlatformAdminProfile)
async def platform_me(
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> PlatformAdminProfile:
    return PlatformAdminProfile(id=str(admin.id), username=admin.username, mobile=admin.mobile)
