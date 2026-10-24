from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.compliance import OutletBusinessDay, OutletCashMovement
from app.models.enums import BillStatus, PaymentMethod
from app.models.order import PosBill, PosBillPayment
from app.models.tenant import BusinessOwner
from app.schemas.owner.settings import (
    BusinessDayResponse,
    CashMovementCreate,
    CashMovementResponse,
    CloseBusinessDayRequest,
    OpenBusinessDayRequest,
)
from app.services.owner.access import get_outlet_for_owner
from app.services.owner.audit_service import TenantAuditService
from app.services.owner.order_pricing import money
from app.services.owner.permissions import (
    PERM_DENIED_MESSAGE,
    PERM_OPS_DAY_CLOSE,
    PERM_OPS_DAY_REOPEN,
    assert_permission,
)
from app.services.owner.sales_analytics_helpers import OUTLET_TZ


class DayCloseService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.audit = TenantAuditService(db)

    def _today(self) -> date:
        return datetime.now(OUTLET_TZ).date()

    async def _get_or_create_day(
        self,
        outlet_id: uuid.UUID,
        business_date: date,
    ) -> OutletBusinessDay:
        result = await self.db.execute(
            select(OutletBusinessDay)
            .where(
                OutletBusinessDay.outlet_id == outlet_id,
                OutletBusinessDay.business_date == business_date,
            )
            .options(selectinload(OutletBusinessDay.movements)),
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = OutletBusinessDay(
                outlet_id=outlet_id,
                business_date=business_date,
                status="open",
                opening_cash=Decimal("0"),
                cash_sales_total=Decimal("0"),
            )
            self.db.add(row)
            await self.db.flush()
        return row

    async def assert_day_open_for_billing(self, outlet_id: uuid.UUID) -> None:
        day = await self._get_or_create_day(outlet_id, self._today())
        if day.status == "closed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Business day is closed. Ask a manager to reopen the day before billing.",
            )

    async def get_today(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
    ) -> BusinessDayResponse:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        day = await self._get_or_create_day(outlet_id, self._today())
        await self._refresh_cash_sales(day)
        return self._to_response(day)

    async def open_day(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        payload: OpenBusinessDayRequest,
    ) -> BusinessDayResponse:
        await assert_permission(self.db, owner, PERM_OPS_DAY_CLOSE, outlet_id)
        await get_outlet_for_owner(self.db, owner, outlet_id)
        day = await self._get_or_create_day(outlet_id, self._today())
        if day.status == "closed":
            try:
                await assert_permission(self.db, owner, PERM_OPS_DAY_REOPEN, outlet_id)
            except HTTPException:
                raise HTTPException(status_code=403, detail=PERM_DENIED_MESSAGE)
            day.status = "open"
            day.closed_at = None
            day.closed_by_owner_id = None
        day.opening_cash = money(payload.opening_cash)
        day.opened_by_owner_id = owner.id
        day.opened_at = datetime.now(timezone.utc)
        await self.audit.log(
            business_id=owner.business_id,
            outlet_id=outlet_id,
            actor=owner,
            action="day.open",
            entity_type="business_day",
            entity_id=str(day.id),
            summary=f"Opened business day with cash float {day.opening_cash}",
        )
        await self.db.commit()
        await self.db.refresh(day)
        return self._to_response(day)

    async def add_movement(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        payload: CashMovementCreate,
    ) -> BusinessDayResponse:
        await assert_permission(self.db, owner, PERM_OPS_DAY_CLOSE, outlet_id)
        await get_outlet_for_owner(self.db, owner, outlet_id)
        day = await self._get_or_create_day(outlet_id, self._today())
        if day.status == "closed":
            raise HTTPException(status_code=409, detail="Day is closed")
        self.db.add(
            OutletCashMovement(
                business_day_id=day.id,
                kind=payload.kind,
                amount=money(payload.amount),
                reason=payload.reason.strip(),
                created_by_owner_id=owner.id,
                created_at=datetime.now(timezone.utc),
            ),
        )
        await self.audit.log(
            business_id=owner.business_id,
            outlet_id=outlet_id,
            actor=owner,
            action="day.cash_movement",
            entity_type="business_day",
            entity_id=str(day.id),
            summary=f"{payload.kind} ₹{payload.amount}",
            reason=payload.reason,
        )
        await self.db.commit()
        day = await self._get_or_create_day(outlet_id, self._today())
        return self._to_response(day)

    async def close_day(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        payload: CloseBusinessDayRequest,
    ) -> BusinessDayResponse:
        await assert_permission(self.db, owner, PERM_OPS_DAY_CLOSE, outlet_id)
        await get_outlet_for_owner(self.db, owner, outlet_id)
        day = await self._get_or_create_day(outlet_id, self._today())
        if day.status == "closed":
            raise HTTPException(status_code=400, detail="Day already closed")
        await self._refresh_cash_sales(day)
        expected = money(day.opening_cash + day.cash_sales_total)
        for m in day.movements:
            if m.kind == "deposit":
                expected = money(expected + m.amount)
            else:
                expected = money(expected - m.amount)
        actual = money(payload.actual_closing_cash)
        day.expected_cash = expected
        day.actual_closing_cash = actual
        day.cash_variance = money(actual - expected)
        day.notes = payload.notes
        day.status = "closed"
        day.closed_by_owner_id = owner.id
        day.closed_at = datetime.now(timezone.utc)
        await self.audit.log(
            business_id=owner.business_id,
            outlet_id=outlet_id,
            actor=owner,
            action="day.close",
            entity_type="business_day",
            entity_id=str(day.id),
            summary=f"Closed day variance {day.cash_variance}",
            detail={"expected": str(expected), "actual": str(actual)},
            reason=payload.notes,
        )
        await self.db.commit()
        await self.db.refresh(day)
        return self._to_response(day)

    async def _refresh_cash_sales(self, day: OutletBusinessDay) -> None:
        start = datetime.combine(day.business_date, datetime.min.time(), tzinfo=OUTLET_TZ)
        end = datetime.combine(day.business_date, datetime.max.time(), tzinfo=OUTLET_TZ)
        result = await self.db.execute(
            select(func.coalesce(func.sum(PosBillPayment.amount), 0))
            .join(PosBill, PosBill.id == PosBillPayment.bill_id)
            .where(
                PosBill.outlet_id == day.outlet_id,
                PosBill.status == BillStatus.SETTLED,
                PosBillPayment.method == PaymentMethod.CASH,
                PosBillPayment.created_at >= start,
                PosBillPayment.created_at <= end,
            ),
        )
        day.cash_sales_total = money(result.scalar_one())

    def _projected_expected(self, day: OutletBusinessDay) -> Decimal:
        expected = money(day.opening_cash + day.cash_sales_total)
        for m in day.movements:
            if m.kind == "deposit":
                expected = money(expected + m.amount)
            else:
                expected = money(expected - m.amount)
        return expected

    def _to_response(self, day: OutletBusinessDay) -> BusinessDayResponse:
        movements = sorted(day.movements, key=lambda m: m.created_at)
        projected = self._projected_expected(day)
        return BusinessDayResponse(
            id=str(day.id),
            business_date=day.business_date.isoformat(),
            status=day.status,
            opening_cash=day.opening_cash,
            expected_cash=day.expected_cash,
            projected_expected_cash=projected,
            actual_closing_cash=day.actual_closing_cash,
            cash_variance=day.cash_variance,
            cash_sales_total=day.cash_sales_total,
            notes=day.notes,
            movements=[
                CashMovementResponse(
                    id=str(m.id),
                    kind=m.kind,
                    amount=m.amount,
                    reason=m.reason,
                    created_at=m.created_at.isoformat(),
                )
                for m in movements
            ],
        )
