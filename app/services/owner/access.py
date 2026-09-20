from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TenantStatus
from app.models.tenant import Business, BusinessOwner, Outlet


async def get_owner_business(db: AsyncSession, owner: BusinessOwner) -> Business:
    result = await db.execute(select(Business).where(Business.id == owner.business_id))
    business = result.scalar_one_or_none()
    if business is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Business not found")
    return business


def assert_business_operational(business: Business) -> None:
    if business.status == TenantStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This venue has been suspended. Contact KhataBabu support.",
        )
    if business.status != TenantStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Business is not active yet.",
        )


async def get_outlet_for_owner(
    db: AsyncSession,
    owner: BusinessOwner,
    outlet_id: uuid.UUID,
) -> Outlet:
    result = await db.execute(
        select(Outlet).where(
            Outlet.id == outlet_id,
            Outlet.business_id == owner.business_id,
        ),
    )
    outlet = result.scalar_one_or_none()
    if outlet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outlet not found")
    return outlet
