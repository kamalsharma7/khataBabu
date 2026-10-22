"""Outlet sales analytics from order lines (KOT, saved bill, or settled)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import OrderLineStatus
from app.models.menu import MenuItem
from app.models.order import PosKot, PosKotLine, PosOrder, PosOrderLine
from app.models.tenant import BusinessOwner
from app.schemas.owner.inventory import (
    InventorySalesAnalyticsResponse,
    ItemQtyRow,
    ItemSalesSummaryRow,
    SalesByDateRow,
    SalesByMonthRow,
    SalesByQuarterRow,
    SalesByWeekRow,
    SalesByWeekdayRow,
    SalesByYearRow,
    SalesOverview,
    SalesWeekendSplit,
)
from app.services.owner.access import get_outlet_for_owner
from app.services.owner.sales_analytics_helpers import (
    OUTLET_TZ,
    bucket_add,
    sale_agg_key,
)
from app.services.owner.order_pricing import money

WEEKDAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def _ensure_item_in_bucket(
    bucket: dict[str, ItemQtyRow],
    menu_item_id: uuid.UUID | None,
    item_name: str,
) -> None:
    key = sale_agg_key(menu_item_id, item_name)
    if key not in bucket:
        bucket[key] = ItemQtyRow(
            menu_item_id=menu_item_id,
            item_name=item_name,
            quantity=Decimal("0"),
        )


def _finalize_bucket(
    bucket: dict[str, ItemQtyRow],
    catalog: list[MenuItem],
    open_names: set[str],
) -> list[ItemQtyRow]:
    for item in catalog:
        _ensure_item_in_bucket(bucket, item.id, item.name)
    for name in sorted(open_names):
        _ensure_item_in_bucket(bucket, None, name)
    return sorted(bucket.values(), key=lambda r: (-float(r.quantity), r.item_name))


def _week_key(local_dt: datetime) -> tuple[str, date]:
    iso = local_dt.isocalendar()
    week_start = local_dt.date() - timedelta(days=local_dt.weekday())
    return f"{iso.year}-W{iso.week:02d}", week_start


def _quarter_key(local_dt: datetime) -> tuple[str, int, int]:
    y = local_dt.year
    q = (local_dt.month - 1) // 3 + 1
    return f"{y}-Q{q}", y, q


class SalesAnalyticsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def build(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        days: int = 30,
    ) -> InventorySalesAnalyticsResponse:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        today = datetime.now(OUTLET_TZ).date()
        from_date = today - timedelta(days=days - 1)

        menu_result = await self.db.execute(
            select(MenuItem)
            .where(MenuItem.outlet_id == outlet_id)
            .order_by(MenuItem.name),
        )
        catalog = list(menu_result.scalars().all())

        kot_at_result = await self.db.execute(
            select(
                PosKotLine.order_line_id,
                func.min(PosKot.created_at),
            )
            .join(PosKot, PosKot.id == PosKotLine.kot_id)
            .where(PosKot.outlet_id == outlet_id)
            .group_by(PosKotLine.order_line_id),
        )
        first_kot_at: dict[uuid.UUID, datetime] = {
            row[0]: row[1] for row in kot_at_result.all()
        }

        lines_result = await self.db.execute(
            select(PosOrderLine, PosOrder)
            .join(PosOrder, PosOrder.id == PosOrderLine.order_id)
            .where(
                PosOrder.outlet_id == outlet_id,
                PosOrderLine.status != OrderLineStatus.CANCELLED,
            ),
        )

        by_day: dict[date, dict[str, ItemQtyRow]] = defaultdict(dict)
        by_weekday: dict[str, dict[str, ItemQtyRow]] = defaultdict(dict)
        by_week: dict[str, dict[str, ItemQtyRow]] = defaultdict(dict)
        week_starts: dict[str, date] = {}
        by_month: dict[str, dict[str, ItemQtyRow]] = defaultdict(dict)
        by_quarter: dict[str, dict[str, ItemQtyRow]] = defaultdict(dict)
        quarter_meta: dict[str, tuple[int, int]] = {}
        by_year: dict[str, dict[str, ItemQtyRow]] = defaultdict(dict)
        weekday_split_bucket: dict[str, ItemQtyRow] = {}
        weekend_split_bucket: dict[str, ItemQtyRow] = {}
        item_totals: dict[str, ItemQtyRow] = {}
        item_weekday: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: Decimal("0")))
        item_weekend: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        item_weekday_only: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        open_names: set[str] = set()
        days_with_sales: set[date] = set()
        line_count = 0

        for line, order in lines_result.all():
            event_at = (
                first_kot_at.get(line.id)
                or order.bill_saved_at
                or order.settled_at
            )
            if event_at is None:
                continue
            if event_at.tzinfo is None:
                event_at = event_at.replace(tzinfo=timezone.utc)
            local_dt = event_at.astimezone(OUTLET_TZ)
            d = local_dt.date()
            if d < from_date or d > today:
                continue

            line_count += 1
            days_with_sales.add(d)
            q = Decimal(line.quantity)
            menu_item_id = line.menu_item_id
            item_name = line.item_name
            if menu_item_id is None:
                open_names.add(item_name.strip())
            key = sale_agg_key(menu_item_id, item_name)

            bucket_add(by_day.setdefault(d, {}), menu_item_id, item_name, q)
            wd = local_dt.strftime("%A")
            bucket_add(by_weekday.setdefault(wd, {}), menu_item_id, item_name, q)

            wk, wk_start = _week_key(local_dt)
            week_starts[wk] = wk_start
            bucket_add(by_week.setdefault(wk, {}), menu_item_id, item_name, q)

            month_key = local_dt.strftime("%Y-%m")
            bucket_add(by_month.setdefault(month_key, {}), menu_item_id, item_name, q)

            qk, qy, qn = _quarter_key(local_dt)
            quarter_meta[qk] = (qy, qn)
            bucket_add(by_quarter.setdefault(qk, {}), menu_item_id, item_name, q)

            year_key = str(local_dt.year)
            bucket_add(by_year.setdefault(year_key, {}), menu_item_id, item_name, q)
            bucket_add(item_totals, menu_item_id, item_name, q)

            item_weekday[key][wd] += q
            if local_dt.weekday() >= 5:
                item_weekend[key] += q
                bucket_add(weekend_split_bucket, menu_item_id, item_name, q)
            else:
                item_weekday_only[key] += q
                bucket_add(weekday_split_bucket, menu_item_id, item_name, q)

        d = from_date
        while d <= today:
            by_day.setdefault(d, {})
            d += timedelta(days=1)

        for wd in WEEKDAYS:
            by_weekday.setdefault(wd, {})

        by_day_rows = [
            SalesByDateRow(
                date=d,
                total_quantity=money(sum(r.quantity for r in _finalize_bucket(by_day[d], catalog, open_names))),
                items=_finalize_bucket(by_day[d], catalog, open_names),
            )
            for d in sorted(by_day.keys())
        ]

        by_weekday_rows = [
            SalesByWeekdayRow(
                weekday=wd,
                is_weekend=wd in ("Saturday", "Sunday"),
                total_quantity=money(
                    sum(r.quantity for r in _finalize_bucket(by_weekday[wd], catalog, open_names)),
                ),
                items=_finalize_bucket(by_weekday[wd], catalog, open_names),
            )
            for wd in WEEKDAYS
        ]

        by_week_rows = [
            SalesByWeekRow(
                week=wk,
                week_start=week_starts[wk],
                total_quantity=money(sum(r.quantity for r in _finalize_bucket(by_week[wk], catalog, open_names))),
                items=_finalize_bucket(by_week[wk], catalog, open_names),
            )
            for wk in sorted(by_week.keys())
        ]

        by_month_rows = [
            SalesByMonthRow(
                month=m,
                total_quantity=money(sum(r.quantity for r in _finalize_bucket(by_month[m], catalog, open_names))),
                items=_finalize_bucket(by_month[m], catalog, open_names),
            )
            for m in sorted(by_month.keys())
        ]

        by_quarter_rows = [
            SalesByQuarterRow(
                quarter=qk,
                year=quarter_meta[qk][0],
                quarter_num=quarter_meta[qk][1],
                total_quantity=money(
                    sum(r.quantity for r in _finalize_bucket(by_quarter[qk], catalog, open_names)),
                ),
                items=_finalize_bucket(by_quarter[qk], catalog, open_names),
            )
            for qk in sorted(by_quarter.keys())
        ]

        by_year_rows = [
            SalesByYearRow(
                year=y,
                total_quantity=money(sum(r.quantity for r in _finalize_bucket(by_year[y], catalog, open_names))),
                items=_finalize_bucket(by_year[y], catalog, open_names),
            )
            for y in sorted(by_year.keys())
        ]

        wd_items = _finalize_bucket(weekday_split_bucket, catalog, open_names)
        we_items = _finalize_bucket(weekend_split_bucket, catalog, open_names)
        weekend_split_row = SalesWeekendSplit(
            weekday_total=money(sum(r.quantity for r in wd_items)),
            weekend_total=money(sum(r.quantity for r in we_items)),
            weekday_items=wd_items,
            weekend_items=we_items,
        )

        catalog_keys: list[tuple[str, uuid.UUID | None, str]] = [
            (sale_agg_key(item.id, item.name), item.id, item.name) for item in catalog
        ]
        for name in sorted(open_names):
            catalog_keys.append((sale_agg_key(None, name), None, name))

        by_item_rows: list[ItemSalesSummaryRow] = []
        for key, mid, name in catalog_keys:
            total_row = item_totals.get(key)
            total_q = total_row.quantity if total_row else Decimal("0")
            by_item_rows.append(
                ItemSalesSummaryRow(
                    menu_item_id=mid,
                    item_name=name,
                    total_quantity=total_q,
                    by_weekday=[
                        ItemQtyRow(
                            menu_item_id=mid,
                            item_name=wd,
                            quantity=money(item_weekday[key].get(wd, Decimal("0"))),
                        )
                        for wd in WEEKDAYS
                    ],
                    weekend_quantity=money(item_weekend.get(key, Decimal("0"))),
                    weekday_quantity=money(item_weekday_only.get(key, Decimal("0"))),
                ),
            )
        by_item_rows.sort(key=lambda r: (-float(r.total_quantity), r.item_name))

        total_units = money(sum(r.total_quantity for r in by_item_rows))
        overview = SalesOverview(
            menu_items_in_catalog=len(catalog),
            open_item_names=len(open_names),
            order_lines_counted=line_count,
            active_sale_days=len(days_with_sales),
            total_units_sold=total_units,
            weekday_units=weekend_split_row.weekday_total,
            weekend_units=weekend_split_row.weekend_total,
        )

        return InventorySalesAnalyticsResponse(
            from_date=from_date,
            to_date=today,
            overview=overview,
            by_day=by_day_rows,
            by_weekday=by_weekday_rows,
            by_week=by_week_rows,
            by_month=by_month_rows,
            by_quarter=by_quarter_rows,
            by_year=by_year_rows,
            weekend_split=weekend_split_row,
            by_item=by_item_rows,
            top_items=by_item_rows[:20],
        )
