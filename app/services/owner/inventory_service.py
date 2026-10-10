from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inventory import InventoryItem, InventoryTransaction, MenuItemInventoryLink
from app.models.order import PosOrderLine
from app.models.tenant import BusinessOwner
from app.schemas.owner.inventory import (
    InventoryAnalyticsResponse,
    InventoryDayBucket,
    InventoryItemCreate,
    InventoryItemResponse,
    InventoryItemUpdate,
    MenuInventoryLinkInput,
)
from app.services.owner.access import assert_business_operational, get_outlet_for_owner
from app.services.owner.order_pricing import money


class OwnerInventoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_items(self, owner: BusinessOwner, outlet_id: uuid.UUID) -> list[InventoryItem]:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        result = await self.db.execute(
            select(InventoryItem)
            .where(InventoryItem.outlet_id == outlet_id)
            .order_by(InventoryItem.name),
        )
        return list(result.scalars().all())

    async def create_item(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        payload: InventoryItemCreate,
    ) -> InventoryItem:
        assert_business_operational(owner.business)
        await get_outlet_for_owner(self.db, owner, outlet_id)
        item = InventoryItem(
            outlet_id=outlet_id,
            name=payload.name.strip(),
            unit=payload.unit.strip() or "pcs",
            current_stock=money(payload.opening_stock),
            low_stock_threshold=payload.low_stock_threshold,
        )
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def update_item(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        item_id: uuid.UUID,
        payload: InventoryItemUpdate,
    ) -> InventoryItem:
        assert_business_operational(owner.business)
        item = await self._get_item(owner, outlet_id, item_id)
        if payload.name is not None:
            item.name = payload.name.strip()
        if payload.unit is not None:
            item.unit = payload.unit.strip() or item.unit
        if payload.low_stock_threshold is not None:
            item.low_stock_threshold = payload.low_stock_threshold
        if payload.adjust_stock_delta is not None:
            delta = money(payload.adjust_stock_delta)
            item.current_stock = money(item.current_stock + delta)
            self.db.add(
                InventoryTransaction(
                    inventory_item_id=item.id,
                    outlet_id=outlet_id,
                    delta=delta,
                    reason="adjustment",
                    notes=payload.adjustment_notes,
                ),
            )
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def link_menu_item(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        menu_item_id: uuid.UUID,
        payload: MenuInventoryLinkInput,
    ) -> None:
        assert_business_operational(owner.business)
        await get_outlet_for_owner(self.db, owner, outlet_id)
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

    async def analytics(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        days: int = 90,
    ) -> InventoryAnalyticsResponse:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        since = datetime.now(timezone.utc) - timedelta_days(days)
        result = await self.db.execute(
            select(InventoryTransaction)
            .where(
                InventoryTransaction.outlet_id == outlet_id,
                InventoryTransaction.created_at >= since,
                InventoryTransaction.delta < 0,
            )
            .order_by(InventoryTransaction.created_at.desc()),
        )
        txs = list(result.scalars().all())
        by_dow: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        by_month: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for tx in txs:
            used = money(-tx.delta)
            dow = tx.created_at.strftime("%A")
            by_dow[dow] += used
            month_key = tx.created_at.strftime("%Y-%m")
            by_month[month_key] += used
        items = await self.list_items(owner, outlet_id)
        return InventoryAnalyticsResponse(
            items=[InventoryItemResponse.model_validate(i) for i in items],
            usage_by_weekday=[
                InventoryDayBucket(label=k, total_qty=v) for k, v in sorted(by_dow.items())
            ],
            usage_by_month=[
                InventoryDayBucket(label=k, total_qty=v) for k, v in sorted(by_month.items())
            ],
        )

    async def deduct_for_order_lines(
        self,
        outlet_id: uuid.UUID,
        lines: list[PosOrderLine],
    ) -> None:
        menu_ids = [line.menu_item_id for line in lines if line.menu_item_id]
        if not menu_ids:
            return
        result = await self.db.execute(
            select(MenuItemInventoryLink)
            .where(MenuItemInventoryLink.menu_item_id.in_(menu_ids))
            .options(selectinload(MenuItemInventoryLink.inventory_item)),
        )
        links_by_menu: dict[uuid.UUID, list[MenuItemInventoryLink]] = defaultdict(list)
        for link in result.scalars().all():
            links_by_menu[link.menu_item_id].append(link)
        for line in lines:
            if not line.menu_item_id:
                continue
            for link in links_by_menu.get(line.menu_item_id, []):
                need = money(link.qty_per_serve * line.quantity)
                inv = link.inventory_item
                inv.current_stock = money(inv.current_stock - need)
                self.db.add(
                    InventoryTransaction(
                        inventory_item_id=inv.id,
                        outlet_id=outlet_id,
                        delta=-need,
                        reason="sale",
                        order_line_id=line.id,
                    ),
                )

    async def check_stock_for_line(
        self,
        outlet_id: uuid.UUID,
        menu_item_id: uuid.UUID,
        quantity: int,
    ) -> list[str]:
        result = await self.db.execute(
            select(MenuItemInventoryLink)
            .where(MenuItemInventoryLink.menu_item_id == menu_item_id)
            .options(selectinload(MenuItemInventoryLink.inventory_item)),
        )
        warnings: list[str] = []
        for link in result.scalars().all():
            need = money(link.qty_per_serve * quantity)
            if link.inventory_item.current_stock < need:
                warnings.append(
                    f"{link.inventory_item.name}: need {need} {link.inventory_item.unit}, "
                    f"have {link.inventory_item.current_stock}",
                )
        return warnings

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


def timedelta_days(days: int):
    from datetime import timedelta

    return timedelta(days=days)
