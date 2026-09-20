from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.security import create_owner_access_token, hash_password, verify_password
from app.models.enums import TenantStatus
from app.models.tenant import BusinessOwner
from app.schemas.owner.auth import (
    OwnerChangePasswordRequest,
    OwnerProfileResponse,
    OwnerTokenResponse,
)


class OwnerAuthService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def login(self, username: str, password: str) -> OwnerTokenResponse:
        result = await self.db.execute(
            select(BusinessOwner)
            .where(BusinessOwner.username == username)
            .options(selectinload(BusinessOwner.business)),
        )
        owner = result.scalar_one_or_none()
        if owner is None or not owner.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        if not verify_password(password, owner.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        business = owner.business
        if business.status == TenantStatus.SUSPENDED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This venue has been suspended. Contact KhataBabu support.",
            )

        token = create_owner_access_token(self.settings, owner.id, owner.business_id)
        return OwnerTokenResponse(
            access_token=token,
            expires_in_minutes=self.settings.owner_access_token_expire_minutes,
            must_change_password=owner.must_change_password,
        )

    async def profile(self, owner: BusinessOwner) -> OwnerProfileResponse:
        business = owner.business
        return OwnerProfileResponse(
            id=str(owner.id),
            username=owner.username,
            full_name=owner.full_name,
            email=owner.email,
            mobile=owner.mobile,
            business_id=str(owner.business_id),
            business_name=business.legal_name,
            business_status=business.status.value,
            must_change_password=owner.must_change_password,
        )

    async def change_password(
        self,
        owner: BusinessOwner,
        payload: OwnerChangePasswordRequest,
    ) -> None:
        if not verify_password(payload.current_password, owner.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect",
            )
        owner.password_hash = hash_password(payload.new_password)
        owner.must_change_password = False
        await self.db.commit()
