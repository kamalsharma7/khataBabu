from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import create_platform_access_token, verify_password
from app.models.platform_admin import PlatformAdmin, PlatformAuditLog
from app.schemas.platform.auth import PlatformTokenResponse


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PlatformAuthService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def _get_admin_by_username(self, username: str) -> PlatformAdmin | None:
        result = await self.db.execute(
            select(PlatformAdmin).where(PlatformAdmin.username == username),
        )
        return result.scalar_one_or_none()

    async def _assert_not_locked(self, admin: PlatformAdmin) -> None:
        if admin.locked_until and admin.locked_until > _utcnow():
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account temporarily locked. Try again later.",
            )

    async def login(self, username: str, password: str) -> PlatformTokenResponse:
        admin = await self._get_admin_by_username(username)
        if admin is None or not admin.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        await self._assert_not_locked(admin)

        if not verify_password(password, admin.password_hash):
            admin.failed_password_attempts += 1
            if admin.failed_password_attempts >= self.settings.platform_max_password_attempts:
                admin.locked_until = _utcnow() + timedelta(
                    minutes=self.settings.platform_lockout_minutes,
                )
                admin.failed_password_attempts = 0
            await self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        admin.failed_password_attempts = 0
        admin.locked_until = None
        admin.last_login_at = _utcnow()

        token = create_platform_access_token(self.settings, admin.id)
        audit = PlatformAuditLog(
            admin_id=admin.id,
            action="platform_login_ok",
            resource_type="platform_admin",
            resource_id=str(admin.id),
        )
        self.db.add(audit)
        await self.db.commit()

        return PlatformTokenResponse(
            access_token=token,
            expires_in_minutes=self.settings.platform_access_token_expire_minutes,
        )
