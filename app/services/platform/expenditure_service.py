from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PlatformExpenditureCategory, SalesEmploymentStatus
from app.models.platform_admin import PlatformAdmin
from app.models.platform_expenditure import PlatformExpenditure
from app.models.platform_sales import PlatformSalesEmployee
from app.schemas.platform.expenditure import (
    CategoryTotal,
    ExpenditureCreate,
    ExpenditureResponse,
    ExpenditureSummary,
    ExpenditureUpdate,
)

_ALL_CATEGORIES = list(PlatformExpenditureCategory)

_SALARY_ELIGIBLE_EMPLOYMENT = frozenset(
    {
        SalesEmploymentStatus.ACTIVE,
        SalesEmploymentStatus.PART_TIME,
        SalesEmploymentStatus.PROBATION,
    },
)


def _day_start(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=timezone.utc)


def _day_end(d: date) -> datetime:
    return datetime.combine(d, time.max, tzinfo=timezone.utc)


def _to_response(row: PlatformExpenditure, sales_employee_name: str | None) -> ExpenditureResponse:
    return ExpenditureResponse(
        id=row.id,
        category=row.category,
        amount_inr=row.amount_inr,
        title=row.title,
        notes=row.notes,
        spent_at=row.spent_at,
        recorded_by_admin_id=row.recorded_by_admin_id,
        sales_employee_id=row.sales_employee_id,
        sales_employee_name=sales_employee_name,
        created_at=row.created_at,
    )


class PlatformExpenditureService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _date_filters(
        self,
        from_date: date | None,
        to_date: date | None,
    ) -> list:
        clauses = []
        if from_date is not None:
            clauses.append(PlatformExpenditure.spent_at >= _day_start(from_date))
        if to_date is not None:
            clauses.append(PlatformExpenditure.spent_at <= _day_end(to_date))
        return clauses

    def _sales_employee_filter(self, sales_employee_id: uuid.UUID | None) -> list:
        if sales_employee_id is None:
            return []
        return [PlatformExpenditure.sales_employee_id == sales_employee_id]

    async def _get_sales_employee(self, employee_id: uuid.UUID) -> PlatformSalesEmployee:
        result = await self.db.execute(
            select(PlatformSalesEmployee).where(PlatformSalesEmployee.id == employee_id),
        )
        employee = result.scalar_one_or_none()
        if employee is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sales employee not found",
            )
        return employee

    async def _get_salary_eligible_sales_employee(
        self,
        employee_id: uuid.UUID,
    ) -> PlatformSalesEmployee:
        employee = await self._get_sales_employee(employee_id)
        if employee.employment_status not in _SALARY_ELIGIBLE_EMPLOYMENT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Salary can only be recorded for sales employees with employment "
                    "status active, part-time, or probation"
                ),
            )
        return employee

    async def list_expenditures(
        self,
        category: PlatformExpenditureCategory | None,
        from_date: date | None,
        to_date: date | None,
        sales_employee_id: uuid.UUID | None = None,
        limit: int = 500,
    ) -> list[ExpenditureResponse]:
        stmt = (
            select(PlatformExpenditure, PlatformSalesEmployee.full_name)
            .outerjoin(
                PlatformSalesEmployee,
                PlatformExpenditure.sales_employee_id == PlatformSalesEmployee.id,
            )
            .order_by(
                PlatformExpenditure.spent_at.desc(),
                PlatformExpenditure.created_at.desc(),
            )
        )
        if category is not None:
            stmt = stmt.where(PlatformExpenditure.category == category)
        for clause in self._date_filters(from_date, to_date):
            stmt = stmt.where(clause)
        for clause in self._sales_employee_filter(sales_employee_id):
            stmt = stmt.where(clause)
        stmt = stmt.limit(min(limit, 1000))
        result = await self.db.execute(stmt)
        rows = result.all()
        return [_to_response(row, name) for row, name in rows]

    async def summary(
        self,
        from_date: date | None,
        to_date: date | None,
        sales_employee_id: uuid.UUID | None = None,
    ) -> ExpenditureSummary:
        agg_stmt = select(
            func.coalesce(func.sum(PlatformExpenditure.amount_inr), 0),
            func.count(PlatformExpenditure.id),
        )
        for clause in self._date_filters(from_date, to_date):
            agg_stmt = agg_stmt.where(clause)
        for clause in self._sales_employee_filter(sales_employee_id):
            agg_stmt = agg_stmt.where(clause)
        agg = await self.db.execute(agg_stmt)
        grand_total, entry_count = agg.one()

        by_cat: list[CategoryTotal] = []
        for cat in _ALL_CATEGORIES:
            cat_stmt = select(
                func.coalesce(func.sum(PlatformExpenditure.amount_inr), 0),
                func.count(PlatformExpenditure.id),
            ).where(PlatformExpenditure.category == cat)
            for clause in self._date_filters(from_date, to_date):
                cat_stmt = cat_stmt.where(clause)
            for clause in self._sales_employee_filter(sales_employee_id):
                cat_stmt = cat_stmt.where(clause)
            row = await self.db.execute(cat_stmt)
            total, count = row.one()
            by_cat.append(
                CategoryTotal(
                    category=cat,
                    total_inr=Decimal(str(total)),
                    entry_count=int(count),
                ),
            )

        return ExpenditureSummary(
            from_date=from_date,
            to_date=to_date,
            grand_total_inr=Decimal(str(grand_total)),
            entry_count=int(entry_count),
            by_category=by_cat,
        )

    async def create(
        self,
        payload: ExpenditureCreate,
        admin: PlatformAdmin,
    ) -> ExpenditureResponse:
        sales_name: str | None = None
        sales_id: uuid.UUID | None = None
        if payload.sales_employee_id is not None:
            employee = await self._get_salary_eligible_sales_employee(payload.sales_employee_id)
            sales_id = employee.id
            sales_name = employee.full_name

        spent_at = payload.spent_at or datetime.now(timezone.utc)
        if spent_at.tzinfo is None:
            spent_at = spent_at.replace(tzinfo=timezone.utc)
        row = PlatformExpenditure(
            category=payload.category,
            amount_inr=payload.amount_inr,
            title=payload.title,
            notes=payload.notes.strip() if payload.notes else None,
            spent_at=spent_at,
            recorded_by_admin_id=admin.id,
            sales_employee_id=sales_id,
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return _to_response(row, sales_name)

    async def update(
        self,
        expenditure_id: uuid.UUID,
        payload: ExpenditureUpdate,
    ) -> ExpenditureResponse:
        result = await self.db.execute(
            select(PlatformExpenditure).where(PlatformExpenditure.id == expenditure_id),
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
        if payload.amount_inr is not None:
            row.amount_inr = payload.amount_inr
        if payload.title is not None:
            row.title = payload.title
        if payload.notes is not None:
            row.notes = payload.notes.strip() or None
        if payload.spent_at is not None:
            spent_at = payload.spent_at
            if spent_at.tzinfo is None:
                spent_at = spent_at.replace(tzinfo=timezone.utc)
            row.spent_at = spent_at
        if payload.sales_employee_id is not None:
            if row.category != PlatformExpenditureCategory.SALES_TEAM_SALARY:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="sales_employee_id only applies to sales team salary entries",
                )
            await self._get_salary_eligible_sales_employee(payload.sales_employee_id)
            row.sales_employee_id = payload.sales_employee_id

        await self.db.commit()
        await self.db.refresh(row)

        sales_name: str | None = None
        if row.sales_employee_id is not None:
            emp = await self._get_sales_employee(row.sales_employee_id)
            sales_name = emp.full_name
        return _to_response(row, sales_name)

    async def delete(self, expenditure_id: uuid.UUID) -> None:
        result = await self.db.execute(
            select(PlatformExpenditure).where(PlatformExpenditure.id == expenditure_id),
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
        await self.db.delete(row)
        await self.db.commit()
