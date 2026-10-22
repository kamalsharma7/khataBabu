from __future__ import annotations

import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import SalesEmploymentStatus
from app.models.platform_sales import PlatformSalesEmployee
from app.models.tenant import Business, Outlet
from app.schemas.platform.sales_employee import (
    SalesEmployeeCreate,
    SalesEmployeeDetailResponse,
    SalesEmployeeResponse,
    SalesEmployeeUpdate,
    SalesEmployeeVenueSummary,
)


def _sync_active_flag(row: PlatformSalesEmployee) -> None:
    row.is_active = row.employment_status == SalesEmploymentStatus.ACTIVE


class PlatformSalesEmployeeService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _venue_counts(self) -> dict[uuid.UUID, int]:
        result = await self.db.execute(
            select(Business.assigned_sales_employee_id, func.count(Business.id))
            .where(Business.assigned_sales_employee_id.is_not(None))
            .group_by(Business.assigned_sales_employee_id),
        )
        return {row[0]: int(row[1]) for row in result.all() if row[0] is not None}

    def _to_response(
        self,
        row: PlatformSalesEmployee,
        counts: dict[uuid.UUID, int],
    ) -> SalesEmployeeResponse:
        return SalesEmployeeResponse(
            id=row.id,
            employee_code=row.employee_code,
            full_name=row.full_name,
            mobile=row.mobile,
            aadhaar_number=row.aadhaar_number,
            pan_number=row.pan_number,
            is_active=row.is_active,
            date_of_joining=row.date_of_joining,
            employment_status=row.employment_status,
            behavior_status=row.behavior_status,
            professional_status=row.professional_status,
            venues_onboarded_count=counts.get(row.id, 0),
        )

    async def list_employees(self, active_only: bool = True) -> list[SalesEmployeeResponse]:
        stmt = select(PlatformSalesEmployee).order_by(PlatformSalesEmployee.full_name)
        if active_only:
            stmt = stmt.where(
                PlatformSalesEmployee.employment_status == SalesEmploymentStatus.ACTIVE,
            )
        result = await self.db.execute(stmt)
        rows = list(result.scalars().all())
        counts = await self._venue_counts()
        return [self._to_response(row, counts) for row in rows]

    async def get_employee(self, employee_id: uuid.UUID) -> SalesEmployeeDetailResponse:
        result = await self.db.execute(
            select(PlatformSalesEmployee).where(PlatformSalesEmployee.id == employee_id),
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

        businesses = await self.db.execute(
            select(Business)
            .where(Business.assigned_sales_employee_id == employee_id)
            .order_by(Business.created_at.desc()),
        )
        biz_list = list(businesses.scalars().all())
        venue_rows: list[SalesEmployeeVenueSummary] = []
        for business in biz_list:
            outlets = await self.db.execute(
                select(Outlet).where(Outlet.business_id == business.id).limit(1),
            )
            outlet = outlets.scalar_one_or_none()
            if outlet is None:
                continue
            venue_rows.append(
                SalesEmployeeVenueSummary(
                    business_id=business.id,
                    legal_name=business.legal_name,
                    outlet_name=outlet.name,
                    outlet_ref_code=outlet.ref_code,
                    status=business.status,
                    city=business.city,
                    state=business.state,
                    created_at=business.created_at.isoformat(),
                ),
            )

        counts = {employee_id: len(venue_rows)}
        base = self._to_response(row, counts)
        return SalesEmployeeDetailResponse(**base.model_dump(), onboarded_venues=venue_rows)

    async def create(self, payload: SalesEmployeeCreate) -> SalesEmployeeResponse:
        code = payload.employee_code.strip().upper()
        dup = await self.db.execute(
            select(PlatformSalesEmployee.id).where(
                (PlatformSalesEmployee.employee_code == code)
                | (PlatformSalesEmployee.mobile == payload.mobile),
            ),
        )
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Employee code or mobile exists")
        joining = payload.date_of_joining or date.today()
        row = PlatformSalesEmployee(
            employee_code=code,
            full_name=payload.full_name.strip(),
            mobile=payload.mobile,
            aadhaar_number=payload.aadhaar_number,
            pan_number=payload.pan_number,
            date_of_joining=joining,
            employment_status=payload.employment_status,
            behavior_status=payload.behavior_status,
            professional_status=payload.professional_status,
        )
        _sync_active_flag(row)
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        counts = await self._venue_counts()
        return self._to_response(row, counts)

    async def update(
        self,
        employee_id: uuid.UUID,
        payload: SalesEmployeeUpdate,
    ) -> SalesEmployeeResponse:
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
        if payload.aadhaar_number is not None:
            row.aadhaar_number = payload.aadhaar_number
        if payload.pan_number is not None:
            row.pan_number = payload.pan_number
        if payload.date_of_joining is not None:
            row.date_of_joining = payload.date_of_joining
        if payload.employment_status is not None:
            row.employment_status = payload.employment_status
        if payload.behavior_status is not None:
            row.behavior_status = payload.behavior_status
        if payload.professional_status is not None:
            row.professional_status = payload.professional_status
        if payload.is_active is not None:
            row.is_active = payload.is_active
            if payload.is_active and row.employment_status != SalesEmploymentStatus.ACTIVE:
                row.employment_status = SalesEmploymentStatus.ACTIVE
            if not payload.is_active and row.employment_status == SalesEmploymentStatus.ACTIVE:
                row.employment_status = SalesEmploymentStatus.BLOCKED
        elif payload.employment_status is not None:
            _sync_active_flag(row)
        await self.db.commit()
        await self.db.refresh(row)
        counts = await self._venue_counts()
        return self._to_response(row, counts)
