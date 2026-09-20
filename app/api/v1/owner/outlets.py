from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.owner import get_current_owner
from app.db.deps import get_db
from app.models.tenant import BusinessOwner, Outlet
from app.schemas.owner.outlet import OutletSummary

router = APIRouter()


@router.get("", response_model=list[OutletSummary])
async def list_outlets(
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> list[OutletSummary]:
    result = await db.execute(
        select(Outlet)
        .where(Outlet.business_id == owner.business_id)
        .order_by(Outlet.name),
    )
    outlets = result.scalars().all()
    return [
        OutletSummary(
            id=o.id,
            name=o.name,
            ref_code=o.ref_code,
            status=o.status.value,
        )
        for o in outlets
    ]


@router.get("/{outlet_id}", response_model=OutletSummary)
async def get_outlet(
    outlet_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> OutletSummary:
    result = await db.execute(
        select(Outlet).where(
            Outlet.id == outlet_id,
            Outlet.business_id == owner.business_id,
        ),
    )
    outlet = result.scalar_one_or_none()
    if outlet is None:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outlet not found")
    return OutletSummary(
        id=outlet.id,
        name=outlet.name,
        ref_code=outlet.ref_code,
        status=outlet.status.value,
    )
