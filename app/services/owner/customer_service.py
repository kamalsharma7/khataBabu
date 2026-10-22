"""Owner CRM: customer master, POS auto-linking, visit stats and insights."""

from __future__ import annotations

import re
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable, Optional

from fastapi import HTTPException, status
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.customer import Customer
from app.models.enums import BillStatus, FoodType, OrderLineStatus, OrderStatus, OrderType, PaymentMethod
from app.models.order import PosBill, PosBillPayment, PosOrder, PosOrderLine
from app.models.tenant import BusinessOwner
from app.models.venue import VenueTable
from app.schemas.owner.customer import (
    CrmInsightsResponse,
    CustomerBackfillResponse,
    CustomerCreate,
    CustomerDetail,
    CustomerFavouriteItem,
    CustomerListResponse,
    CustomerLookupResponse,
    CustomerSummary,
    CustomerUpdate,
    CustomerVisit,
    DaypartCount,
    FrequencyBucket,
    LocalityInsight,
    MonthlyNewCustomers,
    OccasionEntry,
    OrderTypeMix,
    PaymentMixEntry,
    SegmentCount,
    TrendingItem,
    WeekdayCount,
)
from app.services.owner.access import assert_business_operational, get_outlet_for_owner
from app.services.owner.order_pricing import money
from app.services.owner.sales_analytics_helpers import OUTLET_TZ

SEGMENT_LABELS = {
    "vip": "VIP",
    "regular": "Regular",
    "occasional": "Occasional",
    "new": "New",
    "at_risk": "At risk",
    "lost": "Lost",
    "prospect": "No visit yet",
}

WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAYPARTS: list[tuple[str, str, int, int]] = [
    ("breakfast", "Breakfast (6–11)", 6, 11),
    ("lunch", "Lunch (11–15)", 11, 15),
    ("evening", "Evening (15–19)", 15, 19),
    ("dinner", "Dinner (19–23)", 19, 23),
    ("late", "Late night (23–6)", 23, 30),
]

VIP_MIN_VISITS = 10
VIP_MIN_SPEND = Decimal("10000")
AT_RISK_DAYS = 45
LOST_DAYS = 90


def normalize_phone(raw: Optional[str]) -> Optional[str]:
    """Keep digits only; collapse +91 / 0 prefixes to a 10-digit Indian mobile when possible."""
    if raw is None:
        return None
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) < 6:
        return None
    return digits[:20]


def _split_tags(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def _join_tags(tags: Iterable[str]) -> Optional[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        t = tag.strip()[:32]
        if t and t.lower() not in seen:
            seen.add(t.lower())
            cleaned.append(t)
    return ",".join(cleaned)[:512] if cleaned else None


def _clean(value: Optional[str], limit: int) -> Optional[str]:
    if value is None:
        return None
    v = value.strip()
    return v[:limit] if v else None


def segment_for(visit_count: int, total_spend: Decimal, last_visit_at: Optional[datetime], now: datetime) -> str:
    if visit_count <= 0 or last_visit_at is None:
        return "prospect"
    days = (now - last_visit_at).days
    if days > LOST_DAYS:
        return "lost"
    if days > AT_RISK_DAYS and visit_count >= 2:
        return "at_risk"
    if visit_count >= VIP_MIN_VISITS or total_spend >= VIP_MIN_SPEND:
        return "vip"
    if visit_count >= 3:
        return "regular"
    if visit_count == 1:
        return "new"
    return "occasional"


def _daypart_key(local_dt: datetime) -> str:
    h = local_dt.hour
    if h < 6:
        return "late"
    for key, _label, start, end in DAYPARTS:
        if start <= h < end:
            return key
    return "late"


def _pct(part: Decimal | int, whole: Decimal | int) -> Decimal:
    if not whole:
        return Decimal("0")
    return (Decimal(part) * 100 / Decimal(whole)).quantize(Decimal("0.1"))


class OwnerCustomerService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ POS hooks

    async def sync_order_customer(self, order: PosOrder, owner: Optional[BusinessOwner] = None) -> Optional[Customer]:
        """Create/link the customer record from the order's customer fields. No commit."""
        phone = normalize_phone(order.customer_mobile)
        if phone is None:
            # Without a phone we cannot dedupe; keep the order fields but do not link.
            return None
        order.customer_mobile = phone
        customer = await self._get_by_phone(order.outlet_id, phone)
        if customer is None:
            customer = Customer(
                outlet_id=order.outlet_id,
                phone=phone,
                name=_clean(order.customer_name, 128),
                locality=_clean(order.customer_locality, 255),
                relation=order.customer_relation.value if order.customer_relation else None,
                source="pos",
                created_by_owner_id=owner.id if owner else None,
            )
            self.db.add(customer)
            await self.db.flush()
        else:
            name = _clean(order.customer_name, 128)
            if name:
                customer.name = name
            elif customer.name and not order.customer_name:
                order.customer_name = customer.name
            locality = _clean(order.customer_locality, 255)
            if locality:
                customer.locality = locality
            elif customer.locality and not order.customer_locality:
                order.customer_locality = customer.locality
            if order.customer_relation:
                customer.relation = order.customer_relation.value
        order.customer_id = customer.id
        return customer

    async def refresh_stats(self, customer_id: uuid.UUID) -> None:
        """Recompute denormalized visit stats from settled bills. No commit."""
        customer = await self.db.get(Customer, customer_id)
        if customer is None:
            return
        stmt = (
            select(
                func.count(func.distinct(PosOrder.id)),
                func.coalesce(func.sum(PosBill.grand_total - PosBill.refunded_total), 0),
                func.min(PosOrder.settled_at),
                func.max(PosOrder.settled_at),
            )
            .select_from(PosOrder)
            .join(PosBill, PosBill.order_id == PosOrder.id)
            .where(
                PosOrder.customer_id == customer_id,
                PosOrder.status == OrderStatus.SETTLED,
                PosBill.status == BillStatus.SETTLED,
            )
        )
        visits, spend, first_at, last_at = (await self.db.execute(stmt)).one()
        customer.visit_count = int(visits or 0)
        customer.total_spend_inr = money(Decimal(spend or 0))
        customer.first_visit_at = first_at
        customer.last_visit_at = last_at

    # ------------------------------------------------------------------ lookups

    async def _get_by_phone(self, outlet_id: uuid.UUID, phone: str) -> Optional[Customer]:
        result = await self.db.execute(
            select(Customer).where(Customer.outlet_id == outlet_id, Customer.phone == phone),
        )
        return result.scalar_one_or_none()

    async def _get_customer(self, owner: BusinessOwner, outlet_id: uuid.UUID, customer_id: uuid.UUID) -> Customer:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        customer = await self.db.get(Customer, customer_id)
        if customer is None or customer.outlet_id != outlet_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
        return customer

    async def lookup(self, owner: BusinessOwner, outlet_id: uuid.UUID, phone_raw: str) -> CustomerLookupResponse:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        phone = normalize_phone(phone_raw)
        if phone is None:
            return CustomerLookupResponse(found=False)
        customer = await self._get_by_phone(outlet_id, phone)
        if customer is None:
            return CustomerLookupResponse(found=False)
        now = datetime.now(timezone.utc)
        khata = await self._khata_due_map([customer.id])
        summary = self._summary(customer, now, khata.get(customer.id, Decimal("0")))
        favs = await self._favourite_items(customer.id, limit=3)
        greeting = self._greeting(summary, favs)
        return CustomerLookupResponse(
            found=True,
            customer=summary,
            favourite_items=[f.item_name for f in favs],
            greeting=greeting,
        )

    @staticmethod
    def _greeting(summary: CustomerSummary, favs: list[CustomerFavouriteItem]) -> str:
        name = summary.name or "Guest"
        if summary.visit_count == 0:
            return f"{name} is in your CRM but has no settled visit yet."
        bits = [f"{name} · {summary.visit_count} visit{'s' if summary.visit_count != 1 else ''}"]
        if summary.days_since_last_visit is not None:
            if summary.days_since_last_visit == 0:
                bits.append("last visit today")
            else:
                bits.append(f"last visit {summary.days_since_last_visit}d ago")
        if favs:
            bits.append(f"usually orders {favs[0].item_name}")
        if summary.khata_due_inr > 0:
            bits.append(f"khata due ₹{summary.khata_due_inr}")
        return " · ".join(bits)

    async def search(self, owner: BusinessOwner, outlet_id: uuid.UUID, q: str, limit: int = 8) -> list[CustomerSummary]:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        term = q.strip()
        if len(term) < 2:
            return []
        like = f"%{term}%"
        digits = re.sub(r"\D", "", term)
        conds = [Customer.name.ilike(like), Customer.locality.ilike(like)]
        if digits:
            conds.append(Customer.phone.like(f"%{digits}%"))
        result = await self.db.execute(
            select(Customer)
            .where(Customer.outlet_id == outlet_id, or_(*conds))
            .order_by(Customer.last_visit_at.desc().nulls_last(), Customer.created_at.desc())
            .limit(limit),
        )
        rows = list(result.scalars().all())
        now = datetime.now(timezone.utc)
        khata = await self._khata_due_map([c.id for c in rows])
        return [self._summary(c, now, khata.get(c.id, Decimal("0"))) for c in rows]

    # ------------------------------------------------------------------ CRUD

    async def list_customers(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        q: Optional[str],
        segment: Optional[str],
        sort: Optional[str],
        tag: Optional[str],
        limit: int,
        offset: int,
    ) -> CustomerListResponse:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        stmt = select(Customer).where(Customer.outlet_id == outlet_id)
        if q and q.strip():
            like = f"%{q.strip()}%"
            digits = re.sub(r"\D", "", q)
            conds = [Customer.name.ilike(like), Customer.locality.ilike(like), Customer.tags.ilike(like)]
            if digits:
                conds.append(Customer.phone.like(f"%{digits}%"))
            stmt = stmt.where(or_(*conds))
        if tag and tag.strip():
            stmt = stmt.where(Customer.tags.ilike(f"%{tag.strip()}%"))
        rows = list((await self.db.execute(stmt)).scalars().all())

        now = datetime.now(timezone.utc)
        khata = await self._khata_due_map([c.id for c in rows])
        summaries = [self._summary(c, now, khata.get(c.id, Decimal("0"))) for c in rows]
        if segment and segment != "all":
            summaries = [s for s in summaries if s.segment == segment]

        sort_key = sort or "last_visit"
        if sort_key == "visits":
            summaries.sort(key=lambda s: (s.visit_count, s.total_spend_inr), reverse=True)
        elif sort_key == "spend":
            summaries.sort(key=lambda s: (s.total_spend_inr, s.visit_count), reverse=True)
        elif sort_key == "name":
            summaries.sort(key=lambda s: (s.name or "zzz").lower())
        elif sort_key == "created":
            summaries.sort(key=lambda s: s.created_at, reverse=True)
        else:
            far_past = datetime(1970, 1, 1, tzinfo=timezone.utc)
            summaries.sort(key=lambda s: (s.last_visit_at or s.created_at or far_past), reverse=True)

        total = len(summaries)
        page = summaries[offset : offset + limit]
        return CustomerListResponse(total=total, customers=page)

    async def create_customer(self, owner: BusinessOwner, outlet_id: uuid.UUID, payload: CustomerCreate) -> CustomerDetail:
        assert_business_operational(owner.business)
        await get_outlet_for_owner(self.db, owner, outlet_id)
        phone = normalize_phone(payload.phone)
        name = _clean(payload.name, 128)
        if not phone and not name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a name or a mobile number")
        if phone and await self._get_by_phone(outlet_id, phone):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A customer with this mobile already exists")
        customer = Customer(
            outlet_id=outlet_id,
            name=name,
            phone=phone,
            email=_clean(payload.email, 255),
            locality=_clean(payload.locality, 255),
            address=_clean(payload.address, 1024),
            birthday=payload.birthday,
            anniversary=payload.anniversary,
            relation=payload.relation.value if payload.relation else None,
            tags=_join_tags(payload.tags),
            notes=_clean(payload.notes, 2048),
            marketing_opt_in=payload.marketing_opt_in,
            source="manual",
            created_by_owner_id=owner.id,
        )
        self.db.add(customer)
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A customer with this mobile already exists")
        return await self.get_customer(owner, outlet_id, customer.id)

    async def update_customer(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        customer_id: uuid.UUID,
        payload: CustomerUpdate,
    ) -> CustomerDetail:
        assert_business_operational(owner.business)
        customer = await self._get_customer(owner, outlet_id, customer_id)
        if payload.phone is not None:
            phone = normalize_phone(payload.phone)
            if phone != customer.phone:
                if phone and await self._get_by_phone(outlet_id, phone):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Another customer already uses this mobile",
                    )
                customer.phone = phone
        if payload.name is not None:
            customer.name = _clean(payload.name, 128)
        if payload.email is not None:
            customer.email = _clean(payload.email, 255)
        if payload.locality is not None:
            customer.locality = _clean(payload.locality, 255)
        if payload.address is not None:
            customer.address = _clean(payload.address, 1024)
        if payload.birthday is not None:
            customer.birthday = payload.birthday
        if payload.clear_birthday:
            customer.birthday = None
        if payload.anniversary is not None:
            customer.anniversary = payload.anniversary
        if payload.clear_anniversary:
            customer.anniversary = None
        if payload.relation is not None:
            customer.relation = payload.relation.value
        if payload.tags is not None:
            customer.tags = _join_tags(payload.tags)
        if payload.notes is not None:
            customer.notes = _clean(payload.notes, 2048)
        if payload.marketing_opt_in is not None:
            customer.marketing_opt_in = payload.marketing_opt_in
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Another customer already uses this mobile")
        return await self.get_customer(owner, outlet_id, customer_id)

    async def delete_customer(self, owner: BusinessOwner, outlet_id: uuid.UUID, customer_id: uuid.UUID) -> None:
        assert_business_operational(owner.business)
        customer = await self._get_customer(owner, outlet_id, customer_id)
        await self.db.delete(customer)
        await self.db.commit()

    # ------------------------------------------------------------------ detail

    async def get_customer(self, owner: BusinessOwner, outlet_id: uuid.UUID, customer_id: uuid.UUID) -> CustomerDetail:
        customer = await self._get_customer(owner, outlet_id, customer_id)
        now = datetime.now(timezone.utc)
        khata = await self._khata_due_map([customer.id])
        summary = self._summary(customer, now, khata.get(customer.id, Decimal("0")))

        orders_stmt = (
            select(PosOrder, PosBill, VenueTable)
            .join(PosBill, PosBill.order_id == PosOrder.id)
            .outerjoin(VenueTable, PosOrder.venue_table_id == VenueTable.id)
            .where(
                PosOrder.customer_id == customer.id,
                PosOrder.status == OrderStatus.SETTLED,
                PosBill.status == BillStatus.SETTLED,
            )
            .order_by(PosOrder.settled_at.desc())
            .options(selectinload(PosBill.payments), selectinload(PosOrder.lines))
        )
        rows = (await self.db.execute(orders_stmt)).all()

        weekday_counts = [0] * 7
        daypart_counts: dict[str, int] = defaultdict(int)
        type_counts: dict[OrderType, int] = defaultdict(int)
        pay_totals: dict[PaymentMethod, Decimal] = defaultdict(lambda: Decimal("0"))
        veg_qty = 0
        total_qty = 0
        guest_sum = 0
        guest_n = 0
        visits: list[CustomerVisit] = []
        seen_orders: set[uuid.UUID] = set()
        settled_dates: list[datetime] = []

        for order, bill, table in rows:
            if order.id not in seen_orders:
                seen_orders.add(order.id)
                when = order.settled_at or order.created_at
                local = when.astimezone(OUTLET_TZ)
                weekday_counts[local.weekday()] += 1
                daypart_counts[_daypart_key(local)] += 1
                type_counts[order.order_type] += 1
                settled_dates.append(when)
                if order.guest_count:
                    guest_sum += order.guest_count
                    guest_n += 1
                for line in order.lines:
                    if line.status.value == "cancelled":
                        continue
                    total_qty += line.quantity
                    if line.food_type == FoodType.VEG:
                        veg_qty += line.quantity
            for p in bill.payments:
                pay_totals[p.method] += Decimal(p.amount)
            if len(visits) < 25:
                live_lines = [l for l in order.lines if l.status.value != "cancelled"]
                names = [f"{l.item_name} ×{l.quantity}" for l in live_lines[:4]]
                extra = len(live_lines) - 4
                summary_txt = ", ".join(names) + (f" +{extra} more" if extra > 0 else "")
                visits.append(
                    CustomerVisit(
                        order_id=order.id,
                        order_number=order.order_number,
                        bill_id=bill.id,
                        bill_number=bill.bill_number,
                        invoice_code=bill.invoice_code,
                        order_type=order.order_type,
                        table_label=order.table_label_snapshot or (table.label if table else None),
                        settled_at=order.settled_at,
                        grand_total=money(Decimal(bill.grand_total) - Decimal(bill.refunded_total or 0)),
                        items_summary=summary_txt,
                        payment_methods=sorted({p.method for p in bill.payments}, key=lambda m: m.value),
                        guest_count=order.guest_count,
                    ),
                )

        pay_total = sum(pay_totals.values(), Decimal("0"))
        payment_mix = [
            PaymentMixEntry(method=m, amount_inr=money(a), share_percent=_pct(a, pay_total))
            for m, a in sorted(pay_totals.items(), key=lambda kv: kv[1], reverse=True)
        ]
        preferred_type = max(type_counts.items(), key=lambda kv: kv[1])[0] if type_counts else None

        avg_gap: Optional[Decimal] = None
        if len(settled_dates) >= 2:
            ordered = sorted(settled_dates)
            span_days = (ordered[-1] - ordered[0]).total_seconds() / 86400
            avg_gap = (Decimal(span_days) / Decimal(len(ordered) - 1)).quantize(Decimal("0.1"))

        favourites = await self._favourite_items(customer.id, limit=6)

        return CustomerDetail(
            **summary.model_dump(),
            address=customer.address,
            notes=customer.notes,
            preferred_order_type=preferred_type,
            veg_share_percent=_pct(veg_qty, total_qty) if total_qty else None,
            avg_guest_count=(Decimal(guest_sum) / Decimal(guest_n)).quantize(Decimal("0.1")) if guest_n else None,
            favourite_items=favourites,
            visits_by_weekday=[
                WeekdayCount(weekday=i, label=WEEKDAY_LABELS[i], visits=weekday_counts[i]) for i in range(7)
            ],
            visits_by_daypart=[
                DaypartCount(key=key, label=label, visits=daypart_counts.get(key, 0)) for key, label, _s, _e in DAYPARTS
            ],
            payment_mix=payment_mix,
            recent_visits=visits,
            avg_days_between_visits=avg_gap,
        )

    async def _favourite_items(self, customer_id: uuid.UUID, limit: int) -> list[CustomerFavouriteItem]:
        stmt = (
            select(
                PosOrderLine.item_name,
                func.count(func.distinct(PosOrder.id)),
                func.coalesce(func.sum(PosOrderLine.quantity), 0),
                func.max(cast(PosOrderLine.menu_item_id, String)),
            )
            .select_from(PosOrderLine)
            .join(PosOrder, PosOrder.id == PosOrderLine.order_id)
            .where(
                PosOrder.customer_id == customer_id,
                PosOrder.status == OrderStatus.SETTLED,
                PosOrderLine.status != OrderLineStatus.CANCELLED,
            )
            .group_by(PosOrderLine.item_name)
            .order_by(func.count(func.distinct(PosOrder.id)).desc(), func.sum(PosOrderLine.quantity).desc())
            .limit(limit)
        )
        rows = (await self.db.execute(stmt)).all()
        return [
            CustomerFavouriteItem(
                item_name=name,
                times_ordered=int(times),
                total_qty=int(qty),
                menu_item_id=uuid.UUID(mid) if mid else None,
            )
            for name, times, qty, mid in rows
        ]

    async def _khata_due_map(self, customer_ids: list[uuid.UUID]) -> dict[uuid.UUID, Decimal]:
        """Amount settled with payment method DUE (udhaar) per customer."""
        if not customer_ids:
            return {}
        stmt = (
            select(PosOrder.customer_id, func.coalesce(func.sum(PosBillPayment.amount), 0))
            .select_from(PosBillPayment)
            .join(PosBill, PosBill.id == PosBillPayment.bill_id)
            .join(PosOrder, PosOrder.id == PosBill.order_id)
            .where(
                PosOrder.customer_id.in_(customer_ids),
                PosBillPayment.method == PaymentMethod.DUE,
                PosBill.status == BillStatus.SETTLED,
            )
            .group_by(PosOrder.customer_id)
        )
        rows = (await self.db.execute(stmt)).all()
        return {cid: money(Decimal(amt or 0)) for cid, amt in rows}

    @staticmethod
    def _summary(customer: Customer, now: datetime, khata_due: Decimal) -> CustomerSummary:
        spend = Decimal(customer.total_spend_inr or 0)
        visits = int(customer.visit_count or 0)
        last = customer.last_visit_at
        return CustomerSummary(
            id=customer.id,
            outlet_id=customer.outlet_id,
            name=customer.name,
            phone=customer.phone,
            email=customer.email,
            locality=customer.locality,
            relation=customer.relation,
            tags=_split_tags(customer.tags),
            birthday=customer.birthday,
            anniversary=customer.anniversary,
            marketing_opt_in=customer.marketing_opt_in,
            source=customer.source,
            visit_count=visits,
            total_spend_inr=money(spend),
            avg_ticket_inr=money(spend / visits) if visits else Decimal("0"),
            first_visit_at=customer.first_visit_at,
            last_visit_at=last,
            days_since_last_visit=(now - last).days if last else None,
            segment=segment_for(visits, spend, last, now),
            khata_due_inr=khata_due,
            created_at=customer.created_at,
        )

    # ------------------------------------------------------------------ insights

    async def insights(self, owner: BusinessOwner, outlet_id: uuid.UUID) -> CrmInsightsResponse:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        now = datetime.now(timezone.utc)
        today_local = now.astimezone(OUTLET_TZ).date()

        customers = list(
            (await self.db.execute(select(Customer).where(Customer.outlet_id == outlet_id))).scalars().all(),
        )
        khata = await self._khata_due_map([c.id for c in customers])
        summaries = [self._summary(c, now, khata.get(c.id, Decimal("0"))) for c in customers]

        total = len(summaries)
        with_phone = sum(1 for s in summaries if s.phone)
        month_start = today_local.replace(day=1)
        last_month_end = month_start - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)

        def _local_date(dt: datetime) -> date:
            return dt.astimezone(OUTLET_TZ).date()

        new_this_month = sum(1 for s in summaries if _local_date(s.created_at) >= month_start)
        new_last_month = sum(
            1 for s in summaries if last_month_start <= _local_date(s.created_at) <= last_month_end
        )
        visited = [s for s in summaries if s.visit_count > 0]
        repeat = [s for s in visited if s.visit_count >= 2]
        total_visits = sum(s.visit_count for s in visited)
        total_spend = sum((s.total_spend_inr for s in visited), Decimal("0"))

        # Capture rate: how many settled orders in last 30d had a customer attached.
        since = now - timedelta(days=30)
        cap_stmt = select(
            func.count(PosOrder.id),
            func.count(PosOrder.customer_id),
        ).where(
            PosOrder.outlet_id == outlet_id,
            PosOrder.status == OrderStatus.SETTLED,
            PosOrder.settled_at >= since,
        )
        settled_30, identified_30 = (await self.db.execute(cap_stmt)).one()

        seg_counts: dict[str, int] = defaultdict(int)
        seg_spend: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for s in summaries:
            seg_counts[s.segment] += 1
            seg_spend[s.segment] += s.total_spend_inr
        segments = [
            SegmentCount(segment=key, label=label, customers=seg_counts.get(key, 0), spend_inr=money(seg_spend.get(key, Decimal("0"))))
            for key, label in SEGMENT_LABELS.items()
        ]

        loc_c: dict[str, int] = defaultdict(int)
        loc_v: dict[str, int] = defaultdict(int)
        loc_s: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for s in summaries:
            key = (s.locality or "").strip()
            if not key:
                continue
            k = key.title()
            loc_c[k] += 1
            loc_v[k] += s.visit_count
            loc_s[k] += s.total_spend_inr
        top_localities = [
            LocalityInsight(locality=k, customers=loc_c[k], visits=loc_v[k], spend_inr=money(loc_s[k]))
            for k in sorted(loc_c, key=lambda k: (loc_v[k], loc_c[k]), reverse=True)[:10]
        ]

        top_spenders = sorted(visited, key=lambda s: s.total_spend_inr, reverse=True)[:10]
        most_frequent = sorted(visited, key=lambda s: (s.visit_count, s.total_spend_inr), reverse=True)[:10]
        win_back = sorted(
            [s for s in summaries if s.segment in ("at_risk", "lost") and s.visit_count >= 2],
            key=lambda s: s.total_spend_inr,
            reverse=True,
        )[:10]

        buckets = [("1 visit", 1, 1), ("2–3 visits", 2, 3), ("4–9 visits", 4, 9), ("10+ visits", 10, 10**9)]
        frequency_buckets = [
            FrequencyBucket(bucket=label, customers=sum(1 for s in visited if lo <= s.visit_count <= hi))
            for label, lo, hi in buckets
        ]

        monthly: list[MonthlyNewCustomers] = []
        cursor = month_start
        months: list[date] = []
        for _ in range(6):
            months.append(cursor)
            cursor = (cursor - timedelta(days=1)).replace(day=1)
        for m in reversed(months):
            nxt = (m + timedelta(days=32)).replace(day=1)
            count = sum(1 for s in summaries if m <= _local_date(s.created_at) < nxt)
            monthly.append(MonthlyNewCustomers(month=m.strftime("%Y-%m"), label=m.strftime("%b %y"), customers=count))

        trend_stmt = (
            select(
                PosOrderLine.item_name,
                func.count(func.distinct(PosOrder.customer_id)),
                func.coalesce(func.sum(PosOrderLine.quantity), 0),
            )
            .select_from(PosOrderLine)
            .join(PosOrder, PosOrder.id == PosOrderLine.order_id)
            .where(
                PosOrder.outlet_id == outlet_id,
                PosOrder.customer_id.is_not(None),
                PosOrder.status == OrderStatus.SETTLED,
                PosOrderLine.status != OrderLineStatus.CANCELLED,
            )
            .group_by(PosOrderLine.item_name)
            .order_by(func.count(func.distinct(PosOrder.customer_id)).desc())
            .limit(8)
        )
        trending = [
            TrendingItem(item_name=name, customers=int(c), total_qty=int(q))
            for name, c, q in (await self.db.execute(trend_stmt)).all()
        ]

        occasions: list[OccasionEntry] = []
        for s in summaries:
            for kind, d in (("birthday", s.birthday), ("anniversary", s.anniversary)):
                if d is None:
                    continue
                try:
                    nxt_d = d.replace(year=today_local.year)
                except ValueError:  # 29 Feb
                    nxt_d = d.replace(year=today_local.year, day=28)
                if nxt_d < today_local:
                    try:
                        nxt_d = d.replace(year=today_local.year + 1)
                    except ValueError:
                        nxt_d = d.replace(year=today_local.year + 1, day=28)
                away = (nxt_d - today_local).days
                if away <= 30:
                    occasions.append(
                        OccasionEntry(customer_id=s.id, name=s.name, phone=s.phone, occasion=kind, on_date=nxt_d, days_away=away),
                    )
        occasions.sort(key=lambda o: o.days_away)

        pattern_stmt = select(PosOrder.order_type, PosOrder.settled_at).where(
            PosOrder.outlet_id == outlet_id,
            PosOrder.customer_id.is_not(None),
            PosOrder.status == OrderStatus.SETTLED,
            PosOrder.settled_at.is_not(None),
        )
        type_counts: dict[OrderType, int] = defaultdict(int)
        weekday_counts = [0] * 7
        daypart_counts: dict[str, int] = defaultdict(int)
        n_pattern = 0
        for otype, settled_at in (await self.db.execute(pattern_stmt)).all():
            n_pattern += 1
            type_counts[otype] += 1
            local = settled_at.astimezone(OUTLET_TZ)
            weekday_counts[local.weekday()] += 1
            daypart_counts[_daypart_key(local)] += 1
        order_type_mix = [
            OrderTypeMix(order_type=t, visits=c, share_percent=_pct(c, n_pattern))
            for t, c in sorted(type_counts.items(), key=lambda kv: kv[1], reverse=True)
        ]

        return CrmInsightsResponse(
            total_customers=total,
            with_phone=with_phone,
            new_this_month=new_this_month,
            new_last_month=new_last_month,
            repeat_customers=len(repeat),
            repeat_rate_percent=_pct(len(repeat), len(visited)),
            avg_visits_per_customer=(Decimal(total_visits) / Decimal(len(visited))).quantize(Decimal("0.1")) if visited else Decimal("0"),
            avg_spend_per_customer_inr=money(total_spend / Decimal(len(visited))) if visited else Decimal("0"),
            identified_orders_30d=int(identified_30 or 0),
            settled_orders_30d=int(settled_30 or 0),
            capture_rate_30d_percent=_pct(int(identified_30 or 0), int(settled_30 or 0)),
            khata_due_total_inr=money(sum(khata.values(), Decimal("0"))),
            segments=segments,
            top_localities=top_localities,
            top_spenders=top_spenders,
            most_frequent=most_frequent,
            win_back=win_back,
            frequency_buckets=frequency_buckets,
            monthly_new=monthly,
            trending_items=trending,
            upcoming_occasions=occasions[:20],
            order_type_mix=order_type_mix,
            visits_by_weekday=[WeekdayCount(weekday=i, label=WEEKDAY_LABELS[i], visits=weekday_counts[i]) for i in range(7)],
            visits_by_daypart=[DaypartCount(key=k, label=lbl, visits=daypart_counts.get(k, 0)) for k, lbl, _s, _e in DAYPARTS],
        )

    # ------------------------------------------------------------------ backfill

    async def backfill(self, owner: BusinessOwner, outlet_id: uuid.UUID) -> CustomerBackfillResponse:
        """Build customer records from historical orders that captured a mobile number."""
        assert_business_operational(owner.business)
        await get_outlet_for_owner(self.db, owner, outlet_id)
        before = (
            await self.db.execute(select(func.count(Customer.id)).where(Customer.outlet_id == outlet_id))
        ).scalar_one()
        stmt = (
            select(PosOrder)
            .where(
                PosOrder.outlet_id == outlet_id,
                PosOrder.customer_id.is_(None),
                PosOrder.customer_mobile.is_not(None),
            )
            .order_by(PosOrder.created_at.asc())
        )
        orders = list((await self.db.execute(stmt)).scalars().all())
        linked = 0
        for order in orders:
            customer = await self.sync_order_customer(order, owner)
            if customer is not None:
                linked += 1
        await self.db.flush()
        ids = list(
            (await self.db.execute(select(Customer.id).where(Customer.outlet_id == outlet_id))).scalars().all(),
        )
        for cid in ids:
            await self.refresh_stats(cid)
        await self.db.commit()
        after = len(ids)
        return CustomerBackfillResponse(
            orders_scanned=len(orders),
            orders_linked=linked,
            customers_created=max(0, after - int(before or 0)),
            customers_refreshed=after,
        )
