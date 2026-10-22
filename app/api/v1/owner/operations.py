from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.permissions import require_permission
from app.db.deps import get_db
from app.models.tenant import BusinessOwner
from app.schemas.owner.settings import (
    BusinessDayResponse,
    CashMovementCreate,
    CloseBusinessDayRequest,
    OpenBusinessDayRequest,
)
from app.services.owner.day_close_service import DayCloseService
from app.services.owner.permissions import PERM_OPS_DAY_CLOSE

router = APIRouter(prefix="/outlets/{outlet_id}/operations", tags=["owner-operations"])


@router.get("/business-day", response_model=BusinessDayResponse)
async def get_business_day(
    outlet_id: uuid.UUID,
    owner: BusinessOwner = Depends(require_permission(PERM_OPS_DAY_CLOSE)),
    db: AsyncSession = Depends(get_db),
) -> BusinessDayResponse:
    return await DayCloseService(db).get_today(owner, outlet_id)


@router.post("/business-day/open", response_model=BusinessDayResponse)
async def open_business_day(
    outlet_id: uuid.UUID,
    body: OpenBusinessDayRequest,
    owner: BusinessOwner = Depends(require_permission(PERM_OPS_DAY_CLOSE)),
    db: AsyncSession = Depends(get_db),
) -> BusinessDayResponse:
    return await DayCloseService(db).open_day(owner, outlet_id, body)


@router.post("/business-day/cash-movement", response_model=BusinessDayResponse)
async def add_cash_movement(
    outlet_id: uuid.UUID,
    body: CashMovementCreate,
    owner: BusinessOwner = Depends(require_permission(PERM_OPS_DAY_CLOSE)),
    db: AsyncSession = Depends(get_db),
) -> BusinessDayResponse:
    return await DayCloseService(db).add_movement(owner, outlet_id, body)


@router.post("/business-day/close", response_model=BusinessDayResponse)
async def close_business_day(
    outlet_id: uuid.UUID,
    body: CloseBusinessDayRequest,
    owner: BusinessOwner = Depends(require_permission(PERM_OPS_DAY_CLOSE)),
    db: AsyncSession = Depends(get_db),
) -> BusinessDayResponse:
    return await DayCloseService(db).close_day(owner, outlet_id, body)
