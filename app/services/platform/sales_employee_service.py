from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_sales import PlatformSalesEmployee
from app.schemas.platform.sales_employee import SalesEmployeeCreate, SalesEmployeeUpdate


class PlatformSalesEmployeeService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_employees(self, active_only: bool = True) -> list[PlatformSalesEmployee]:
        stmt = select(PlatformSalesEmployee).order_by(PlatformSalesEmployee.full_name)
        if active_only:
            stmt = stmt.where(PlatformSalesEmployee.is_active.is_(True))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create(self, payload: SalesEmployeeCreate) -> PlatformSalesEmployee:
        code = payload.employee_code.strip().upper()
        dup = await self.db.execute(
            select(PlatformSalesEmployee.id).where(
                (PlatformSalesEmployee.employee_code == code)
                | (PlatformSalesEmployee.mobile == payload.mobile),
            ),
        )
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Employee code or mobile exists")
        row = PlatformSalesEmployee(
            employee_code=code,
            full_name=payload.full_name.strip(),
            mobile=payload.mobile,
            is_active=True,
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def update(
        self,
        employee_id: uuid.UUID,
        payload: SalesEmployeeUpdate,
    ) -> PlatformSalesEmployee:
        result = await self.db.execute(
            select(PlatformSalesEmployee).where(PlatformSalesEmployee.id == employee_id),
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
        if payload.full_name is not None:
            row.full_name = payload.full_name.strip()
        if payload.mobile is not None:
            row.mobile = payload.mobile
        if payload.is_active is not None:
            row.is_active = payload.is_active
        await self.db.commit()
        await self.db.refresh(row)
        return row
