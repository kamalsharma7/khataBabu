from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.security import create_owner_access_token, hash_password, verify_password
from app.models.enums import OwnerRole, TenantStatus
from app.models.owner_auth import OwnerPasswordResetToken
from app.models.platform_sales import PlatformSalesEmployee
from app.models.tenant import BusinessOwner
from app.schemas.owner.auth import (
    OwnerChangePasswordRequest,
    OwnerForgotPasswordRequest,
    OwnerProfileResponse,
    OwnerResetPasswordRequest,
    OwnerTokenResponse,
)

logger = logging.getLogger(__name__)


def permissions_for_role(role: OwnerRole) -> list[str]:
    if role == OwnerRole.WORKER:
        return ["pos.billing"]
    if role == OwnerRole.ADMIN:
        return [
            "pos.billing",
            "pos.menu",
            "pos.floor",
            "pos.inventory",
            "pos.bills",
            "analytics.overview",
        ]
    return [
        "pos.billing",
        "pos.menu",
        "pos.floor",
        "pos.inventory",
        "pos.bills",
        "analytics.overview",
        "settings.all",
    ]


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
        support_name: str | None = None
        support_mobile: str | None = None
        if business.assigned_sales_employee_id:
            result = await self.db.execute(
                select(PlatformSalesEmployee).where(
                    PlatformSalesEmployee.id == business.assigned_sales_employee_id,
                ),
            )
            sales = result.scalar_one_or_none()
            if sales and sales.is_active:
                support_name = sales.full_name
                support_mobile = sales.mobile
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
            role=owner.role.value,
            permissions=permissions_for_role(owner.role),
            support_contact_name=support_name,
            support_contact_mobile=support_mobile,
        )

    async def request_password_reset(self, payload: OwnerForgotPasswordRequest) -> None:
        username = payload.username.strip().lower()
        result = await self.db.execute(
            select(BusinessOwner).where(BusinessOwner.username == username),
        )
        owner = result.scalar_one_or_none()
        if owner is None or not owner.is_active:
            return
        raw = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        expires = datetime.now(timezone.utc) + timedelta(hours=2)
        self.db.add(
            OwnerPasswordResetToken(
                owner_id=owner.id,
                token_hash=token_hash,
                expires_at=expires,
                created_at=datetime.now(timezone.utc),
            ),
        )
        await self.db.commit()
        logger.info(
            "password_reset_token owner=%s token=%s (deliver via SMS in production)",
            owner.username,
            raw,
        )

    async def reset_password(self, payload: OwnerResetPasswordRequest) -> None:
        token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
        result = await self.db.execute(
            select(OwnerPasswordResetToken)
            .where(
                OwnerPasswordResetToken.token_hash == token_hash,
                OwnerPasswordResetToken.used_at.is_(None),
            )
            .order_by(OwnerPasswordResetToken.created_at.desc())
            .limit(1),
        )
        row = result.scalar_one_or_none()
        if row is None or row.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")
        owner = await self.db.get(BusinessOwner, row.owner_id)
        if owner is None or not owner.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")
        owner.password_hash = hash_password(payload.new_password)
        owner.must_change_password = False
        row.used_at = datetime.now(timezone.utc)
        await self.db.commit()

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
