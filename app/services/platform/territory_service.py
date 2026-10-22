from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.india_territory import normalize_state_city
from app.models.enums import BillStatus, TenantStatus
from app.models.order import PosBill
from app.models.platform_collection import PlatformCollection
from app.models.tenant import Business, Outlet
from app.schemas.platform.territory import (
    TerritoryAnalyticsResponse,
    TerritoryCityRow,
    TerritoryInsightRow,
    TerritoryOutletRow,
    TerritoryRevenueAnalyticsResponse,
    TerritoryRevenueCityRow,
    TerritoryRevenueInsightRow,
    TerritoryRevenueOutletRow,
    TerritoryRevenueStateRow,
    TerritoryStateRow,
)


def _day_start(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=timezone.utc)


def _day_end(d: date) -> datetime:
    return datetime.combine(d, time.max, tzinfo=timezone.utc)


def _money(value: Decimal | float | int) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


class PlatformTerritoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def analytics(
        self,
        from_date: date | None,
        to_date: date | None,
    ) -> TerritoryAnalyticsResponse:
        outlet_rows = await self._load_outlet_business_rows()

        sales_stmt = (
            select(
                PosBill.outlet_id,
                func.coalesce(
                    func.sum(PosBill.grand_total - PosBill.refunded_total),
                    0,
                ),
                func.count(PosBill.id),
            )
            .where(PosBill.status == BillStatus.SETTLED)
            .group_by(PosBill.outlet_id)
        )
        if from_date is not None:
            sales_stmt = sales_stmt.where(PosBill.created_at >= _day_start(from_date))
        if to_date is not None:
            sales_stmt = sales_stmt.where(PosBill.created_at <= _day_end(to_date))

        sales_result = await self.db.execute(sales_stmt)
        sales_by_outlet: dict = {}
        for outlet_id, total, count in sales_result.all():
            sales_by_outlet[outlet_id] = (_money(total), int(count))

        outlet_records: list[TerritoryOutletRow] = []
        for outlet, business in outlet_rows:
            sales, bill_count = sales_by_outlet.get(outlet.id, (Decimal("0"), 0))
            canon_state, canon_city = normalize_state_city(business.state, business.city)
            outlet_records.append(
                TerritoryOutletRow(
                    outlet_id=outlet.id,
                    outlet_name=outlet.name,
                    outlet_ref_code=outlet.ref_code,
                    business_id=business.id,
                    legal_name=business.legal_name,
                    city=canon_city,
                    state=canon_state,
                    status=outlet.status,
                    plan_tier=business.plan_tier.value,
                    gross_sales_inr=sales,
                    settled_bill_count=bill_count,
                ),
            )

        cities_map: dict[tuple[str, str], list[TerritoryOutletRow]] = defaultdict(list)
        for row in outlet_records:
            cities_map[(row.state, row.city)].append(row)

        states_map: dict[str, list[TerritoryCityRow]] = defaultdict(list)
        for (state, city), outlets in sorted(cities_map.items(), key=lambda x: (x[0][0], x[0][1])):
            city_sales = sum((o.gross_sales_inr for o in outlets), Decimal("0"))
            city_bills = sum(o.settled_bill_count for o in outlets)
            active = sum(1 for o in outlets if o.status == TenantStatus.ACTIVE)
            states_map[state].append(
                TerritoryCityRow(
                    city=city,
                    state=state,
                    outlet_count=len(outlets),
                    active_outlet_count=active,
                    gross_sales_inr=_money(city_sales),
                    settled_bill_count=city_bills,
                    outlets=sorted(outlets, key=lambda o: (-o.gross_sales_inr, o.outlet_name)),
                ),
            )

        state_rows: list[TerritoryStateRow] = []
        for state in sorted(states_map.keys()):
            cities = states_map[state]
            state_sales = sum((c.gross_sales_inr for c in cities), Decimal("0"))
            state_bills = sum(c.settled_bill_count for c in cities)
            state_outlets = sum(c.outlet_count for c in cities)
            state_active = sum(c.active_outlet_count for c in cities)
            state_rows.append(
                TerritoryStateRow(
                    state=state,
                    city_count=len(cities),
                    outlet_count=state_outlets,
                    active_outlet_count=state_active,
                    gross_sales_inr=_money(state_sales),
                    settled_bill_count=state_bills,
                    cities=sorted(cities, key=lambda c: (-c.gross_sales_inr, c.city)),
                ),
            )

        state_rows.sort(key=lambda s: (-s.gross_sales_inr, s.state))

        total_outlets = len(outlet_records)
        all_states = {r.state for r in outlet_records}
        all_cities = {(r.state, r.city) for r in outlet_records}
        grand_sales = _money(sum((r.gross_sales_inr for r in outlet_records), Decimal("0")))
        total_bills = sum(r.settled_bill_count for r in outlet_records)
        active_outlets = sum(1 for r in outlet_records if r.status == TenantStatus.ACTIVE)

        insights = self._build_insights(state_rows)

        return TerritoryAnalyticsResponse(
            from_date=from_date,
            to_date=to_date,
            total_outlets=total_outlets,
            total_states=len(all_states),
            total_cities=len(all_cities),
            active_outlets=active_outlets,
            grand_sales_inr=grand_sales,
            settled_bill_count=total_bills,
            states=state_rows,
            insights=insights,
        )

    def _build_insights(self, states: list[TerritoryStateRow]) -> list[TerritoryInsightRow]:
        insights: list[TerritoryInsightRow] = []
        if not states:
            insights.append(
                TerritoryInsightRow(
                    kind="empty",
                    state="",
                    city="",
                    outlet_count=0,
                    gross_sales_inr=Decimal("0"),
                    message="No onboarded outlets yet. Onboard venues to see territory coverage.",
                ),
            )
            return insights

        flat_cities: list[TerritoryCityRow] = []
        for st in states:
            for city in st.cities:
                flat_cities.append(city)

        if flat_cities:
            by_outlets = sorted(flat_cities, key=lambda c: (c.outlet_count, c.gross_sales_inr))
            weakest = by_outlets[0]
            if weakest.outlet_count <= 1:
                insights.append(
                    TerritoryInsightRow(
                        kind="low_coverage",
                        state=weakest.state,
                        city=weakest.city,
                        outlet_count=weakest.outlet_count,
                        gross_sales_inr=weakest.gross_sales_inr,
                        message=(
                            f"Thin coverage in {weakest.city}, {weakest.state} "
                            f"({weakest.outlet_count} outlet). Consider sales focus here."
                        ),
                    ),
                )

            zero_sales = [c for c in flat_cities if c.gross_sales_inr <= 0 and c.outlet_count > 0]
            for city in sorted(zero_sales, key=lambda c: (-c.outlet_count, c.city))[:3]:
                insights.append(
                    TerritoryInsightRow(
                        kind="no_sales",
                        state=city.state,
                        city=city.city,
                        outlet_count=city.outlet_count,
                        gross_sales_inr=city.gross_sales_inr,
                        message=(
                            f"No settled POS sales in period for {city.city}, {city.state} "
                            f"({city.outlet_count} outlet(s))."
                        ),
                    ),
                )

            top = max(flat_cities, key=lambda c: c.gross_sales_inr)
            if top.gross_sales_inr > 0:
                insights.append(
                    TerritoryInsightRow(
                        kind="top_city",
                        state=top.state,
                        city=top.city,
                        outlet_count=top.outlet_count,
                        gross_sales_inr=top.gross_sales_inr,
                        message=f"Strongest city in period: {top.city}, {top.state}.",
                    ),
                )

        low_state = min(states, key=lambda s: (s.outlet_count, s.gross_sales_inr))
        if len(states) > 1 and low_state.outlet_count <= 2:
            insights.append(
                TerritoryInsightRow(
                    kind="weak_state",
                    state=low_state.state,
                    city="",
                    outlet_count=low_state.outlet_count,
                    gross_sales_inr=low_state.gross_sales_inr,
                    message=(
                        f"Weakest state by footprint: {low_state.state} "
                        f"({low_state.outlet_count} outlets, {low_state.city_count} cities)."
                    ),
                ),
            )

        return insights[:8]

    async def _load_outlet_business_rows(self) -> list[tuple[Outlet, Business]]:
        outlets_result = await self.db.execute(
            select(Outlet, Business)
            .join(Business, Outlet.business_id == Business.id)
            .order_by(Business.state, Business.city, Outlet.name),
        )
        return list(outlets_result.all())

    async def revenue_analytics(
        self,
        from_date: date | None,
        to_date: date | None,
    ) -> TerritoryRevenueAnalyticsResponse:
        outlet_rows = await self._load_outlet_business_rows()

        coll_stmt = (
            select(
                PlatformCollection.business_id,
                func.coalesce(func.sum(PlatformCollection.amount_inr), 0),
                func.count(PlatformCollection.id),
            )
            .group_by(PlatformCollection.business_id)
        )
        if from_date is not None:
            coll_stmt = coll_stmt.where(PlatformCollection.payment_date >= from_date)
        if to_date is not None:
            coll_stmt = coll_stmt.where(PlatformCollection.payment_date <= to_date)

        coll_result = await self.db.execute(coll_stmt)
        collections_by_business: dict = {}
        for business_id, total, count in coll_result.all():
            collections_by_business[business_id] = (_money(total), int(count))

        outlet_records: list[TerritoryRevenueOutletRow] = []
        for outlet, business in outlet_rows:
            amount, pack_count = collections_by_business.get(
                business.id,
                (Decimal("0"), 0),
            )
            canon_state, canon_city = normalize_state_city(business.state, business.city)
            outlet_records.append(
                TerritoryRevenueOutletRow(
                    outlet_id=outlet.id,
                    outlet_name=outlet.name,
                    outlet_ref_code=outlet.ref_code,
                    business_id=business.id,
                    legal_name=business.legal_name,
                    city=canon_city,
                    state=canon_state,
                    status=outlet.status,
                    plan_tier=business.plan_tier.value,
                    collections_inr=amount,
                    collection_count=pack_count,
                ),
            )

        cities_map: dict[tuple[str, str], list[TerritoryRevenueOutletRow]] = defaultdict(list)
        for row in outlet_records:
            cities_map[(row.state, row.city)].append(row)

        states_map: dict[str, list[TerritoryRevenueCityRow]] = defaultdict(list)
        for (state, city), outlets in sorted(cities_map.items(), key=lambda x: (x[0][0], x[0][1])):
            city_total = sum((o.collections_inr for o in outlets), Decimal("0"))
            city_packs = sum(o.collection_count for o in outlets)
            active = sum(1 for o in outlets if o.status == TenantStatus.ACTIVE)
            states_map[state].append(
                TerritoryRevenueCityRow(
                    city=city,
                    state=state,
                    outlet_count=len(outlets),
                    active_outlet_count=active,
                    collections_inr=_money(city_total),
                    collection_count=city_packs,
                    outlets=sorted(outlets, key=lambda o: (-o.collections_inr, o.outlet_name)),
                ),
            )

        state_rows: list[TerritoryRevenueStateRow] = []
        for state in sorted(states_map.keys()):
            cities = states_map[state]
            state_total = sum((c.collections_inr for c in cities), Decimal("0"))
            state_packs = sum(c.collection_count for c in cities)
            state_outlets = sum(c.outlet_count for c in cities)
            state_active = sum(c.active_outlet_count for c in cities)
            state_rows.append(
                TerritoryRevenueStateRow(
                    state=state,
                    city_count=len(cities),
                    outlet_count=state_outlets,
                    active_outlet_count=state_active,
                    collections_inr=_money(state_total),
                    collection_count=state_packs,
                    cities=sorted(cities, key=lambda c: (-c.collections_inr, c.city)),
                ),
            )

        state_rows.sort(key=lambda s: (-s.collections_inr, s.state))

        total_outlets = len(outlet_records)
        all_states = {r.state for r in outlet_records}
        all_cities = {(r.state, r.city) for r in outlet_records}
        grand = _money(sum((r.collections_inr for r in outlet_records), Decimal("0")))
        total_packs = sum(r.collection_count for r in outlet_records)
        active_outlets = sum(1 for r in outlet_records if r.status == TenantStatus.ACTIVE)

        insights = self._build_revenue_insights(state_rows)

        return TerritoryRevenueAnalyticsResponse(
            from_date=from_date,
            to_date=to_date,
            total_outlets=total_outlets,
            total_states=len(all_states),
            total_cities=len(all_cities),
            active_outlets=active_outlets,
            grand_collections_inr=grand,
            collection_count=total_packs,
            states=state_rows,
            insights=insights,
        )

    def _build_revenue_insights(
        self,
        states: list[TerritoryRevenueStateRow],
    ) -> list[TerritoryRevenueInsightRow]:
        insights: list[TerritoryRevenueInsightRow] = []
        if not states:
            insights.append(
                TerritoryRevenueInsightRow(
                    kind="empty",
                    state="",
                    city="",
                    outlet_count=0,
                    collections_inr=Decimal("0"),
                    message="No onboarded outlets yet. Record collections to see KhataBabu revenue by territory.",
                ),
            )
            return insights

        flat_cities: list[TerritoryRevenueCityRow] = []
        for st in states:
            for city in st.cities:
                flat_cities.append(city)

        zero_rev = [c for c in flat_cities if c.collections_inr <= 0 and c.outlet_count > 0]
        for city in sorted(zero_rev, key=lambda c: (-c.outlet_count, c.city))[:3]:
            insights.append(
                TerritoryRevenueInsightRow(
                    kind="no_revenue",
                    state=city.state,
                    city=city.city,
                    outlet_count=city.outlet_count,
                    collections_inr=city.collections_inr,
                    message=(
                        f"No collection payments in period for {city.city}, {city.state} "
                        f"({city.outlet_count} outlet(s))."
                    ),
                ),
            )

        top = max(flat_cities, key=lambda c: c.collections_inr)
        if top.collections_inr > 0:
            insights.append(
                TerritoryRevenueInsightRow(
                    kind="top_city",
                    state=top.state,
                    city=top.city,
                    outlet_count=top.outlet_count,
                    collections_inr=top.collections_inr,
                    message=f"Top KhataBabu revenue city in period: {top.city}, {top.state}.",
                ),
            )

        top_state = max(states, key=lambda s: s.collections_inr)
        if top_state.collections_inr > 0:
            insights.append(
                TerritoryRevenueInsightRow(
                    kind="top_state",
                    state=top_state.state,
                    city="",
                    outlet_count=top_state.outlet_count,
                    collections_inr=top_state.collections_inr,
                    message=f"Top state by your revenue: {top_state.state}.",
                ),
            )

        return insights[:8]
