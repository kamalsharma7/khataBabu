from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.platform import get_current_platform_admin
from app.db.deps import get_db
from app.models.enums import PlatformExpenditureCategory
from app.models.platform_admin import PlatformAdmin
from app.schemas.platform.expenditure import (
    ExpenditureCreate,
    ExpenditureResponse,
    ExpenditureSummary,
    ExpenditureUpdate,
)
from app.services.platform.expenditure_service import PlatformExpenditureService

router = APIRouter()


@router.get("/summary", response_model=ExpenditureSummary)
async def expenditure_summary(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    sales_employee_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> ExpenditureSummary:
    service = PlatformExpenditureService(db)
    return await service.summary(from_date, to_date, sales_employee_id=sales_employee_id)


@router.get("", response_model=list[ExpenditureResponse])
async def list_expenditures(
    category: PlatformExpenditureCategory | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    sales_employee_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> list[ExpenditureResponse]:
    service = PlatformExpenditureService(db)
    return await service.list_expenditures(
        category,
        from_date,
        to_date,
        sales_employee_id=sales_employee_id,
        limit=limit,
    )


@router.post("", response_model=ExpenditureResponse, status_code=201)
async def create_expenditure(
    body: ExpenditureCreate,
    db: AsyncSession = Depends(get_db),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> ExpenditureResponse:
    service = PlatformExpenditureService(db)
    return await service.create(body, admin)


@router.patch("/{expenditure_id}", response_model=ExpenditureResponse)
async def update_expenditure(
    expenditure_id: uuid.UUID,
    body: ExpenditureUpdate,
    db: AsyncSession = Depends(get_db),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> ExpenditureResponse:
    service = PlatformExpenditureService(db)
    return await service.update(expenditure_id, body)


@router.delete("/{expenditure_id}", status_code=204)
async def delete_expenditure(
    expenditure_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> None:
    service = PlatformExpenditureService(db)
    await service.delete(expenditure_id)
