from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.owner import get_current_owner
from app.core.config import Settings, get_settings
from app.db.deps import get_db
from app.models.tenant import BusinessOwner
from app.schemas.owner.auth import (
    OwnerChangePasswordRequest,
    OwnerLoginRequest,
    OwnerProfileResponse,
    OwnerTokenResponse,
)
from app.services.owner.auth_service import OwnerAuthService

router = APIRouter()


@router.post("/login", response_model=OwnerTokenResponse)
async def owner_login(
    body: OwnerLoginRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> OwnerTokenResponse:
    service = OwnerAuthService(db, settings)
    return await service.login(body.username, body.password)


@router.get("/me", response_model=OwnerProfileResponse)
async def owner_me(
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> OwnerProfileResponse:
    service = OwnerAuthService(db, settings)
    return await service.profile(owner)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def owner_change_password(
    body: OwnerChangePasswordRequest,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> None:
    service = OwnerAuthService(db, settings)
    await service.change_password(owner, body)
