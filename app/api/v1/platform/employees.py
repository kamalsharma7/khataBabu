from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.platform import get_current_platform_admin
from app.db.deps import get_db
from app.models.platform_admin import PlatformAdmin
from app.schemas.platform.sales_employee import (
    SalesEmployeeCreate,
    SalesEmployeeResponse,
    SalesEmployeeUpdate,
)
from app.services.platform.sales_employee_service import PlatformSalesEmployeeService

router = APIRouter()


@router.get("/sales-employees", response_model=list[SalesEmployeeResponse])
async def list_sales_employees(
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> list[SalesEmployeeResponse]:
    service = PlatformSalesEmployeeService(db)
    rows = await service.list_employees(active_only=active_only)
    return [SalesEmployeeResponse.model_validate(r) for r in rows]


@router.post("/sales-employees", response_model=SalesEmployeeResponse, status_code=status.HTTP_201_CREATED)
async def create_sales_employee(
    body: SalesEmployeeCreate,
    db: AsyncSession = Depends(get_db),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> SalesEmployeeResponse:
    service = PlatformSalesEmployeeService(db)
    row = await service.create(body)
    return SalesEmployeeResponse.model_validate(row)


@router.patch("/sales-employees/{employee_id}", response_model=SalesEmployeeResponse)
async def update_sales_employee(
    employee_id: uuid.UUID,
    body: SalesEmployeeUpdate,
    db: AsyncSession = Depends(get_db),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> SalesEmployeeResponse:
    service = PlatformSalesEmployeeService(db)
    row = await service.update(employee_id, body)
    return SalesEmployeeResponse.model_validate(row)
