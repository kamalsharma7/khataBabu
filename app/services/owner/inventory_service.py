from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inventory import InventoryItem, InventoryTransaction, MenuItemInventoryLink
from app.models.menu import MenuItem
from app.models.enums import OrderLineStatus, OrderStatus
from app.models.order import PosKot, PosKotLine, PosOrder, PosOrderLine
from app.models.tenant import BusinessOwner
from app.schemas.owner.inventory import (
    BulkDailyStockBody,
    InventoryItemCreate,
    InventoryItemResponse,
    InventoryItemUpdate,
    InventorySalesAnalyticsResponse,
    InventoryTransactionResponse,
    LinkedMenuItem,
    MenuInventoryLinkInput,
    ReplaceRecipeBomBody,
    SetDailyStockBody,
    StockAdjustBody,
    TrackMenuStockBody,
)
from app.services.owner.access import assert_business_operational, get_outlet_for_owner
from app.services.owner.order_pricing import money

STOCK_QTY = Decimal("0.001")


def _qty(value: Decimal | int | float | str | None) -> Decimal:
    if value is None:
        value = Decimal("0")
    elif not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(STOCK_QTY)
from app.services.owner.sales_analytics_helpers import OUTLET_TZ
from app.services.owner.sales_analytics_service import SalesAnalyticsService


class OwnerInventoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def outlet_today() -> date:
        return datetime.now(OUTLET_TZ).date()

    @staticmethod
    def _effective_remaining(item: InventoryItem, today: date) -> Decimal:
        if not item.tracks_daily:
            return money(item.current_stock)
        if item.stock_date != today:
            return Decimal("0")
        return money(item.current_stock)

    @staticmethod
    def _sold_today(item: InventoryItem, today: date) -> Decimal:
        if item.stock_date != today or item.today_opening is None:
            return Decimal("0")
        return money(money(item.today_opening) - money(item.current_stock))

    async def _links_for_outlet(self, outlet_id: uuid.UUID) -> dict[uuid.UUID, list[MenuItemInventoryLink]]:
        result = await self.db.execute(
            select(MenuItemInventoryLink)
            .join(InventoryItem, InventoryItem.id == MenuItemInventoryLink.inventory_item_id)
            .where(InventoryItem.outlet_id == outlet_id)
            .options(
                selectinload(MenuItemInventoryLink.inventory_item),
                selectinload(MenuItemInventoryLink.menu_item),
            ),
        )
        by_inv: dict[uuid.UUID, list[MenuItemInventoryLink]] = defaultdict(list)
        for link in result.scalars().all():
            by_inv[link.inventory_item_id].append(link)
        return by_inv

    def _item_response(
        self,
        item: InventoryItem,
        links: list[MenuItemInventoryLink],
        today: date,
    ) -> InventoryItemResponse:
        remaining = self._effective_remaining(item, today)
        sold = self._sold_today(item, today)
        linked = [
            LinkedMenuItem(
                menu_item_id=link.menu_item_id,
                menu_item_name=link.menu_item.name if link.menu_item else "Menu item",
                qty_per_serve=link.qty_per_serve,
            )
            for link in links
        ]
        return InventoryItemResponse(
            id=item.id,
            outlet_id=item.outlet_id,
            name=item.name,
            unit=item.unit,
            category=item.category or "grocery",
            tracks_daily=item.tracks_daily,
            daily_par=item.daily_par,
            stock_date=item.stock_date,
            today_opening=item.today_opening if item.stock_date == today else None,
            remaining_today=remaining,
            sold_today=sold,
            current_stock=_qty(item.current_stock),
            low_stock_threshold=item.low_stock_threshold,
            cost_per_unit=item.cost_per_unit,
            notes=item.notes,
            linked_menu_items=linked,
        )

    async def list_items(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        kind: str = "all",
    ) -> list[InventoryItemResponse]:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        today = self.outlet_today()
        stmt = select(InventoryItem).where(InventoryItem.outlet_id == outlet_id)
        if kind == "raw":
            stmt = stmt.where(InventoryItem.tracks_daily.is_(False))
        elif kind == "daily":
            stmt = stmt.where(InventoryItem.tracks_daily.is_(True))
        stmt = stmt.order_by(InventoryItem.category, InventoryItem.name)
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())
        links_by_inv = await self._links_for_outlet(outlet_id)
        return [self._item_response(i, links_by_inv.get(i.id, []), today) for i in items]

    async def create_item(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        payload: InventoryItemCreate,
    ) -> InventoryItemResponse:
        assert_business_operational(owner.business)
        await get_outlet_for_owner(self.db, owner, outlet_id)
        opening = _qty(payload.opening_stock)
        item = InventoryItem(
            outlet_id=outlet_id,
            name=payload.name.strip(),
            unit=payload.unit.strip() or "pcs",
            category=(payload.category or "grocery").strip().lower(),
            current_stock=opening,
            tracks_daily=payload.tracks_daily,
            daily_par=payload.daily_par,
            low_stock_threshold=payload.low_stock_threshold,
            cost_per_unit=payload.cost_per_unit,
            notes=(payload.notes or "").strip() or None,
        )
        self.db.add(item)
        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A raw material or stock item with this name already exists",
            )
        if opening > 0:
            self.db.add(
                InventoryTransaction(
                    inventory_item_id=item.id,
                    outlet_id=outlet_id,
                    delta=opening,
                    reason="opening",
                    notes="Opening stock",
                ),
            )
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A raw material or stock item with this name already exists",
            )
        await self.db.refresh(item)
        return self._item_response(item, [], self.outlet_today())

    async def update_item(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        item_id: uuid.UUID,
        payload: InventoryItemUpdate,
    ) -> InventoryItemResponse:
        assert_business_operational(owner.business)
        item = await self._get_item(owner, outlet_id, item_id)
        if payload.name is not None:
            item.name = payload.name.strip()
        if payload.unit is not None:
            item.unit = payload.unit.strip() or item.unit
        if payload.daily_par is not None:
            item.daily_par = payload.daily_par
        if payload.tracks_daily is not None:
            item.tracks_daily = payload.tracks_daily
        if payload.low_stock_threshold is not None:
            item.low_stock_threshold = payload.low_stock_threshold
        if payload.category is not None:
            item.category = payload.category.strip().lower() or item.category
        if payload.cost_per_unit is not None:
            item.cost_per_unit = payload.cost_per_unit
        if payload.notes is not None:
            item.notes = payload.notes.strip() or None
        await self.db.commit()
        await self.db.refresh(item)
        links = await self._links_for_outlet(outlet_id)
        return self._item_response(item, links.get(item.id, []), self.outlet_today())

    async def set_daily_stock(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        item_id: uuid.UUID,
        payload: SetDailyStockBody,
    ) -> InventoryItemResponse:
        assert_business_operational(owner.business)
        item = await self._get_item(owner, outlet_id, item_id)
        today = self.outlet_today()
        qty = money(payload.quantity)
        item.stock_date = today
        item.today_opening = qty
        item.current_stock = qty
        if item.daily_par is None:
            item.daily_par = qty
        self.db.add(
            InventoryTransaction(
                inventory_item_id=item.id,
                outlet_id=outlet_id,
                delta=qty,
                reason="daily_opening",
                notes=f"Daily stock set to {qty}",
            ),
        )
        await self.db.commit()
        await self.db.refresh(item)
        links = await self._links_for_outlet(outlet_id)
        return self._item_response(item, links.get(item.id, []), today)

    async def bulk_set_daily_stock(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        payload: BulkDailyStockBody,
    ) -> list[InventoryItemResponse]:
        responses: list[InventoryItemResponse] = []
        for row in payload.items:
            responses.append(
                await self.set_daily_stock(
                    owner,
                    outlet_id,
                    row.inventory_item_id,
                    SetDailyStockBody(quantity=row.quantity),
                ),
            )
        return responses

    async def track_menu_stock(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        payload: TrackMenuStockBody,
    ) -> InventoryItemResponse:
        assert_business_operational(owner.business)
        await get_outlet_for_owner(self.db, owner, outlet_id)
        menu_result = await self.db.execute(
            select(MenuItem).where(
                MenuItem.id == payload.menu_item_id,
                MenuItem.outlet_id == outlet_id,
            ),
        )
        menu = menu_result.scalar_one_or_none()
        if menu is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")

        link_result = await self.db.execute(
            select(MenuItemInventoryLink)
            .where(MenuItemInventoryLink.menu_item_id == menu.id)
            .options(selectinload(MenuItemInventoryLink.inventory_item)),
        )
        link = link_result.scalar_one_or_none()
        if link is None:
            inv = InventoryItem(
                outlet_id=outlet_id,
                name=menu.name.strip(),
                unit=payload.unit.strip() or "pcs",
                current_stock=Decimal("0"),
                tracks_daily=True,
            )
            self.db.add(inv)
            await self.db.flush()
            link = MenuItemInventoryLink(
                menu_item_id=menu.id,
                inventory_item_id=inv.id,
                qty_per_serve=payload.qty_per_kot,
            )
            self.db.add(link)
        else:
            inv = link.inventory_item
            inv.name = menu.name.strip()
            inv.unit = payload.unit.strip() or inv.unit
            link.qty_per_serve = payload.qty_per_kot

        await self.db.flush()
        return await self.set_daily_stock(
            owner,
            outlet_id,
            inv.id,
            SetDailyStockBody(quantity=payload.today_quantity),
        )

    async def delete_item(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> None:
        assert_business_operational(owner.business)
        item = await self._get_item(owner, outlet_id, item_id)
        await self.db.delete(item)
        await self.db.commit()

    async def link_menu_item(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        menu_item_id: uuid.UUID,
        payload: MenuInventoryLinkInput,
    ) -> None:
        assert_business_operational(owner.business)
        await get_outlet_for_owner(self.db, owner, outlet_id)
        menu = await self.db.execute(
            select(MenuItem).where(MenuItem.id == menu_item_id, MenuItem.outlet_id == outlet_id),
        )
        if menu.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")
        inv = await self._get_item(owner, outlet_id, payload.inventory_item_id)
        existing = await self.db.execute(
            select(MenuItemInventoryLink).where(
                MenuItemInventoryLink.menu_item_id == menu_item_id,
                MenuItemInventoryLink.inventory_item_id == inv.id,
            ),
        )
        link = existing.scalar_one_or_none()
        if link is None:
            link = MenuItemInventoryLink(
                menu_item_id=menu_item_id,
                inventory_item_id=inv.id,
                qty_per_serve=payload.qty_per_serve,
            )
            self.db.add(link)
        else:
            link.qty_per_serve = payload.qty_per_serve
        await self.db.commit()

    async def unlink_menu_item(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        menu_item_id: uuid.UUID,
        inventory_item_id: uuid.UUID,
    ) -> None:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        result = await self.db.execute(
            select(MenuItemInventoryLink).where(
                MenuItemInventoryLink.menu_item_id == menu_item_id,
                MenuItemInventoryLink.inventory_item_id == inventory_item_id,
            ),
        )
        link = result.scalar_one_or_none()
        if link is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
        await self.db.delete(link)
        await self.db.commit()

    async def replace_raw_bom(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        menu_item_id: uuid.UUID,
        payload: ReplaceRecipeBomBody,
    ) -> None:
        """Replace recipe BOM links (raw materials only) for a menu item."""
        assert_business_operational(owner.business)
        await get_outlet_for_owner(self.db, owner, outlet_id)
        menu = await self.db.execute(
            select(MenuItem).where(MenuItem.id == menu_item_id, MenuItem.outlet_id == outlet_id),
        )
        if menu.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")

        wanted: dict[uuid.UUID, Decimal] = {}
        for line in payload.lines:
            inv = await self._get_item(owner, outlet_id, line.inventory_item_id)
            if inv.tracks_daily:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{inv.name} is daily dish stock, not a raw material",
                )
            wanted[inv.id] = _qty(line.qty_per_serve)

        existing = await self.db.execute(
            select(MenuItemInventoryLink)
            .join(InventoryItem, InventoryItem.id == MenuItemInventoryLink.inventory_item_id)
            .where(
                MenuItemInventoryLink.menu_item_id == menu_item_id,
                InventoryItem.tracks_daily.is_(False),
            ),
        )
        existing_links = list(existing.scalars().all())
        keep_ids = set(wanted.keys())
        for link in existing_links:
            if link.inventory_item_id not in keep_ids:
                await self.db.delete(link)
            else:
                link.qty_per_serve = wanted[link.inventory_item_id]
                wanted.pop(link.inventory_item_id, None)
        for inv_id, qty in wanted.items():
            self.db.add(
                MenuItemInventoryLink(
                    menu_item_id=menu_item_id,
                    inventory_item_id=inv_id,
                    qty_per_serve=qty,
                ),
            )
        await self.db.commit()

    async def adjust_stock(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        item_id: uuid.UUID,
        payload: StockAdjustBody,
    ) -> InventoryItemResponse:
        assert_business_operational(owner.business)
        item = await self._get_item(owner, outlet_id, item_id)
        amount = _qty(payload.quantity)
        reason = payload.reason
        if reason == "purchase":
            if amount <= 0:
                raise HTTPException(status_code=400, detail="Purchase quantity must be greater than 0")
            delta = amount
        elif reason == "wastage":
            if amount <= 0:
                raise HTTPException(status_code=400, detail="Wastage quantity must be greater than 0")
            delta = -amount
        elif reason == "opening":
            if amount < 0:
                raise HTTPException(status_code=400, detail="Opening stock cannot be negative")
            delta = _qty(amount - _qty(item.current_stock))
        else:
            delta = amount

        next_stock = _qty(_qty(item.current_stock) + delta)
        if next_stock < 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Not enough {item.name} in stock ({item.current_stock} {item.unit})",
            )
        item.current_stock = next_stock
        self.db.add(
            InventoryTransaction(
                inventory_item_id=item.id,
                outlet_id=outlet_id,
                delta=delta,
                reason=reason,
                notes=(payload.notes or "").strip() or None,
            ),
        )
        await self.db.commit()
        await self.db.refresh(item)
        links = await self._links_for_outlet(outlet_id)
        return self._item_response(item, links.get(item.id, []), self.outlet_today())

    async def list_transactions(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        item_id: uuid.UUID,
        limit: int = 50,
    ) -> list[InventoryTransactionResponse]:
        await self._get_item(owner, outlet_id, item_id)
        result = await self.db.execute(
            select(InventoryTransaction)
            .where(
                InventoryTransaction.inventory_item_id == item_id,
                InventoryTransaction.outlet_id == outlet_id,
            )
            .order_by(InventoryTransaction.created_at.desc())
            .limit(limit),
        )
        rows = list(result.scalars().all())
        return [
            InventoryTransactionResponse(
                id=tx.id,
                inventory_item_id=tx.inventory_item_id,
                delta=tx.delta,
                reason=tx.reason,
                notes=tx.notes,
                created_at=tx.created_at,
            )
            for tx in rows
        ]

    async def sales_analytics(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        days: int = 30,
    ) -> InventorySalesAnalyticsResponse:
        return await SalesAnalyticsService(self.db).build(owner, outlet_id, days)

    async def _pending_need_for_inventory(
        self,
        outlet_id: uuid.UUID,
        inventory_item_id: uuid.UUID,
    ) -> Decimal:
        """Units already on open orders (pending KOT) for menu items linked to this stock."""
        link_result = await self.db.execute(
            select(MenuItemInventoryLink).where(
                MenuItemInventoryLink.inventory_item_id == inventory_item_id,
            ),
        )
        menu_ids = [link.menu_item_id for link in link_result.scalars().all()]
        if not menu_ids:
            return Decimal("0")
        line_result = await self.db.execute(
            select(PosOrderLine)
            .join(PosOrder, PosOrder.id == PosOrderLine.order_id)
            .where(
                PosOrder.outlet_id == outlet_id,
                PosOrder.status == OrderStatus.OPEN,
                PosOrderLine.status == OrderLineStatus.PENDING_KOT,
                PosOrderLine.menu_item_id.in_(menu_ids),
            ),
        )
        pending_lines = list(line_result.scalars().all())
        needs = await self._inventory_needs_for_lines(pending_lines)
        for inv, qty in needs.values():
            if inv.id == inventory_item_id:
                return qty
        return Decimal("0")

    async def _inventory_needs_for_lines(
        self,
        lines: list[PosOrderLine],
    ) -> dict[uuid.UUID, tuple[InventoryItem, Decimal]]:
        menu_ids = [line.menu_item_id for line in lines if line.menu_item_id]
        if not menu_ids:
            return {}
        result = await self.db.execute(
            select(MenuItemInventoryLink)
            .where(MenuItemInventoryLink.menu_item_id.in_(menu_ids))
            .options(selectinload(MenuItemInventoryLink.inventory_item)),
        )
        links_by_menu: dict[uuid.UUID, list[MenuItemInventoryLink]] = defaultdict(list)
        for link in result.scalars().all():
            links_by_menu[link.menu_item_id].append(link)

        needs: dict[uuid.UUID, tuple[InventoryItem, Decimal]] = {}
        for line in lines:
            if not line.menu_item_id:
                continue
            for link in links_by_menu.get(line.menu_item_id, []):
                inv = link.inventory_item
                need = money(link.qty_per_serve * line.quantity)
                if inv.id in needs:
                    prev_inv, prev_need = needs[inv.id]
                    needs[inv.id] = (prev_inv, money(prev_need + need))
                else:
                    needs[inv.id] = (inv, need)
        return needs

    async def assert_stock_for_lines(self, outlet_id: uuid.UUID, lines: list[PosOrderLine]) -> None:
        today = self.outlet_today()
        needs = await self._inventory_needs_for_lines(lines)
        errors: list[str] = []
        checked: set[uuid.UUID] = set()
        for inv, _need in needs.values():
            if inv.id in checked:
                continue
            checked.add(inv.id)
            if not inv.tracks_daily:
                total_pending = await self._pending_need_for_inventory(outlet_id, inv.id)
                if money(inv.current_stock) < total_pending:
                    errors.append(
                        f"{inv.name} is out of inventory (need {total_pending}, have {inv.current_stock})",
                    )
                continue
            if inv.stock_date != today or inv.today_opening is None:
                errors.append(f"{inv.name}: daily stock not set for today")
                continue
            remaining = self._effective_remaining(inv, today)
            total_pending = await self._pending_need_for_inventory(outlet_id, inv.id)
            if remaining < total_pending:
                errors.append(
                    f"{inv.name} is out of inventory for today (need {total_pending}, {remaining} left)",
                )
        if errors:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"inventory": errors, "message": "; ".join(errors)},
            )

    async def check_stock_for_line(
        self,
        outlet_id: uuid.UUID,
        menu_item_id: uuid.UUID,
        quantity_on_order: int,
        _order_id: uuid.UUID,
    ) -> list[str]:
        """quantity_on_order = total pending qty for this menu item on the current order after add."""
        today = self.outlet_today()
        warnings: list[str] = []
        link_result = await self.db.execute(
            select(MenuItemInventoryLink)
            .where(MenuItemInventoryLink.menu_item_id == menu_item_id)
            .options(selectinload(MenuItemInventoryLink.inventory_item)),
        )
        links = list(link_result.scalars().all())
        for link in links:
            inv = link.inventory_item
            per_unit = money(link.qty_per_serve)
            this_order_need = money(per_unit * quantity_on_order)
            other_pending = await self._pending_need_for_inventory(outlet_id, inv.id)
            other_only = money(other_pending - this_order_need)
            if other_only < 0:
                other_only = Decimal("0")
            total_need = money(other_only + this_order_need)
            if not inv.tracks_daily:
                if money(inv.current_stock) < total_need:
                    warnings.append(f"{inv.name} is out of inventory")
                continue
            if inv.stock_date != today or inv.today_opening is None:
                warnings.append(f"{inv.name}: set today's stock in Inventory")
                continue
            remaining = self._effective_remaining(inv, today)
            if remaining < total_need:
                warnings.append(f"{inv.name} is out of inventory for today ({remaining} left)")
        return warnings

    async def deduct_for_order_lines(
        self,
        outlet_id: uuid.UUID,
        lines: list[PosOrderLine],
        *,
        reason: str = "kot",
    ) -> None:
        for line in lines:
            if not line.menu_item_id:
                continue
            existing = await self.db.execute(
                select(func.count())
                .select_from(InventoryTransaction)
                .where(
                    InventoryTransaction.order_line_id == line.id,
                    InventoryTransaction.reason == reason,
                ),
            )
            if existing.scalar_one() > 0:
                continue
            for link in await self._links_for_menu(line.menu_item_id):
                need = money(link.qty_per_serve * line.quantity)
                inv = link.inventory_item
                inv.current_stock = money(inv.current_stock - need)
                self.db.add(
                    InventoryTransaction(
                        inventory_item_id=inv.id,
                        outlet_id=outlet_id,
                        delta=-need,
                        reason=reason,
                        order_line_id=line.id,
                    ),
                )

    async def _links_for_menu(self, menu_item_id: uuid.UUID) -> list[MenuItemInventoryLink]:
        result = await self.db.execute(
            select(MenuItemInventoryLink)
            .where(MenuItemInventoryLink.menu_item_id == menu_item_id)
            .options(selectinload(MenuItemInventoryLink.inventory_item)),
        )
        return list(result.scalars().all())

    async def restore_for_order_line(
        self,
        outlet_id: uuid.UUID,
        line: PosOrderLine,
    ) -> None:
        result = await self.db.execute(
            select(InventoryTransaction).where(
                InventoryTransaction.order_line_id == line.id,
                InventoryTransaction.reason == "kot",
                InventoryTransaction.delta < 0,
            ),
        )
        for tx in result.scalars().all():
            inv = await self.db.get(InventoryItem, tx.inventory_item_id)
            if inv is None:
                continue
            restore = money(-tx.delta)
            inv.current_stock = money(inv.current_stock + restore)
            self.db.add(
                InventoryTransaction(
                    inventory_item_id=inv.id,
                    outlet_id=outlet_id,
                    delta=restore,
                    reason="kot_void",
                    order_line_id=line.id,
                    notes="Restored from cancelled KOT line",
                ),
            )

    async def _get_item(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> InventoryItem:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        result = await self.db.execute(
            select(InventoryItem).where(
                InventoryItem.id == item_id,
                InventoryItem.outlet_id == outlet_id,
            ),
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found")
        return item
