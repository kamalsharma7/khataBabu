from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.security import (
    create_owner_analytics_token,
    hash_password,
    verify_password,
)
from app.models.enums import BillStatus, OrderStatus, PaymentMethod
from app.models.order import PosBill, PosBillPayment, PosOrder
from app.models.tenant import Business, BusinessOwner
from app.models.venue import VenueTable
from app.schemas.owner.analytics import (
    AnalyticsOrderRow,
    AnalyticsOrdersResponse,
    AnalyticsPaymentBreakdown,
    AnalyticsStatusResponse,
    AnalyticsSummaryResponse,
    AnalyticsUnlockResponse,
)
from app.services.owner.access import get_outlet_for_owner
from app.services.owner.order_pricing import money
from app.services.owner.order_service import historical_table_label


class OwnerAnalyticsService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def status(self, owner: BusinessOwner, outlet_id: uuid.UUID) -> AnalyticsStatusResponse:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        business = await self._load_business(owner.business_id)
        return AnalyticsStatusResponse(pin_configured=business.analytics_pin_hash is not None)

    async def unlock(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        *,
        pin: str | None,
        login_password: str | None,
        new_pin: str | None,
    ) -> AnalyticsUnlockResponse:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        business = await self._load_business(owner.business_id)

        if business.analytics_pin_hash is None:
            if not login_password or not verify_password(login_password, owner.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Login password required to set overview PIN",
                )
            if not new_pin or len(new_pin.strip()) < 4:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Choose a new overview PIN (at least 4 characters)",
                )
            business.analytics_pin_hash = hash_password(new_pin.strip())
            await self.db.commit()
            await self.db.refresh(business)
        else:
            allowed = False
            pin_value = (pin or "").strip()
            login_value = (login_password or "").strip()
            if not pin_value and not login_value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Enter your overview PIN or login password",
                )
            if pin_value and verify_password(pin_value, business.analytics_pin_hash):
                allowed = True
            if login_value and verify_password(login_value, owner.password_hash):
                allowed = True
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid overview PIN or password",
                )

        token = create_owner_analytics_token(
            self.settings,
            owner.id,
            owner.business_id,
            outlet_id,
        )
        return AnalyticsUnlockResponse(
            analytics_token=token,
            expires_in_minutes=self.settings.owner_analytics_token_expire_minutes,
            pin_configured=business.analytics_pin_hash is not None,
        )

    async def summary(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        from_dt: datetime,
        to_dt: datetime,
    ) -> AnalyticsSummaryResponse:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        if from_dt > to_dt:
            raise HTTPException(status_code=400, detail="from_datetime must be before to_datetime")

        bill_filters = (
            PosOrder.outlet_id == outlet_id,
            PosOrder.status == OrderStatus.SETTLED,
            PosOrder.settled_at.isnot(None),
            PosOrder.settled_at >= from_dt,
            PosOrder.settled_at <= to_dt,
            PosBill.status == BillStatus.SETTLED,
        )

        agg = await self.db.execute(
            select(
                func.count(PosOrder.id),
                func.coalesce(func.sum(PosBill.grand_total), 0),
                func.coalesce(func.sum(PosBill.discount_amount), 0),
                func.coalesce(func.sum(PosBill.tax_amount), 0),
                func.coalesce(
                    func.sum(case((PosOrder.pay_later.is_(True), 1), else_=0)),
                    0,
                ),
            )
            .select_from(PosOrder)
            .join(PosBill, PosBill.order_id == PosOrder.id)
            .where(*bill_filters),
        )
        row = agg.one()
        orders_settled = int(row[0] or 0)
        gross = money(row[1])
        discount_total = money(row[2])
        tax_total = money(row[3])
        pay_later_settled = int(row[4] or 0)

        cancelled = await self.db.execute(
            select(func.count(PosOrder.id)).where(
                PosOrder.outlet_id == outlet_id,
                PosOrder.status == OrderStatus.CANCELLED,
                PosOrder.cancelled_at.isnot(None),
                PosOrder.cancelled_at >= from_dt,
                PosOrder.cancelled_at <= to_dt,
            ),
        )
        orders_cancelled = int(cancelled.scalar() or 0)

        open_now = await self.db.execute(
            select(func.count(PosOrder.id)).where(
                PosOrder.outlet_id == outlet_id,
                PosOrder.status == OrderStatus.OPEN,
            ),
        )
        open_orders_now = int(open_now.scalar() or 0)

        payment_rows = await self.db.execute(
            select(
                PosBillPayment.method,
                func.coalesce(func.sum(PosBillPayment.amount), 0),
                func.count(PosBillPayment.id),
            )
            .join(PosBill, PosBillPayment.bill_id == PosBill.id)
            .join(PosOrder, PosBill.order_id == PosOrder.id)
            .where(*bill_filters)
            .group_by(PosBillPayment.method),
        )
        breakdown: list[AnalyticsPaymentBreakdown] = []
        total_collected = Decimal("0")
        for method, amount, count in payment_rows.all():
            amt = money(amount)
            total_collected += amt
            breakdown.append(
                AnalyticsPaymentBreakdown(
                    method=method,
                    amount=amt,
                    count=int(count or 0),
                ),
            )
        breakdown.sort(key=lambda x: x.amount, reverse=True)

        average = money(gross / orders_settled) if orders_settled else Decimal("0")

        return AnalyticsSummaryResponse(
            from_datetime=from_dt,
            to_datetime=to_dt,
            gross_sales=gross,
            total_collected=total_collected,
            discount_total=discount_total,
            tax_total=tax_total,
            orders_settled=orders_settled,
            orders_cancelled=orders_cancelled,
            average_bill=average,
            pay_later_settled=pay_later_settled,
            open_orders_now=open_orders_now,
            payment_breakdown=breakdown,
        )

    async def list_orders(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        from_dt: datetime,
        to_dt: datetime,
        offset: int,
        limit: int,
    ) -> AnalyticsOrdersResponse:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        if from_dt > to_dt:
            raise HTTPException(status_code=400, detail="from_datetime must be before to_datetime")

        base = (
            select(PosOrder, PosBill, VenueTable)
            .join(PosBill, PosBill.order_id == PosOrder.id)
            .outerjoin(VenueTable, PosOrder.venue_table_id == VenueTable.id)
            .where(
                PosOrder.outlet_id == outlet_id,
                PosOrder.status == OrderStatus.SETTLED,
                PosOrder.settled_at.isnot(None),
                PosOrder.settled_at >= from_dt,
                PosOrder.settled_at <= to_dt,
                PosBill.status == BillStatus.SETTLED,
            )
            .options(selectinload(PosBill.payments))
            .order_by(PosOrder.settled_at.desc())
        )

        total = int(
            (
                await self.db.execute(
                    select(func.count(PosOrder.id))
                    .select_from(PosOrder)
                    .join(PosBill, PosBill.order_id == PosOrder.id)
                    .where(
                        PosOrder.outlet_id == outlet_id,
                        PosOrder.status == OrderStatus.SETTLED,
                        PosOrder.settled_at.isnot(None),
                        PosOrder.settled_at >= from_dt,
                        PosOrder.settled_at <= to_dt,
                        PosBill.status == BillStatus.SETTLED,
                    ),
                )
            ).scalar()
            or 0,
        )

        result = await self.db.execute(base.offset(offset).limit(limit))
        items: list[AnalyticsOrderRow] = []
        for order, bill, table in result.all():
            pay_parts = [
                f"{p.method.value} {money(p.amount)}" for p in sorted(bill.payments, key=lambda x: x.created_at)
            ]
            items.append(
                AnalyticsOrderRow(
                    order_id=order.id,
                    order_number=order.order_number,
                    bill_number=bill.bill_number,
                    settled_at=order.settled_at,
                    table_label=historical_table_label(order, table),
                    customer_name=order.customer_name,
                    guest_count=order.guest_count,
                    subtotal=money(bill.subtotal),
                    discount_amount=money(bill.discount_amount),
                    tax_amount=money(bill.tax_amount),
                    grand_total=money(bill.grand_total),
                    pay_later=order.pay_later,
                    payments_summary=" · ".join(pay_parts) if pay_parts else "—",
                ),
            )

        return AnalyticsOrdersResponse(total=total, items=items)

    async def _load_business(self, business_id: uuid.UUID) -> Business:
        result = await self.db.execute(select(Business).where(Business.id == business_id))
        business = result.scalar_one_or_none()
        if business is None:
            raise HTTPException(status_code=404, detail="Business not found")
        return business
