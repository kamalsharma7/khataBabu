from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import (
    BillStatus,
    KotStatus,
    OrderLineStatus,
    OrderStatus,
    OrderType,
    TableVisualState,
)
from app.models.menu import MenuItem, MenuItemAddon, MenuItemVariation
from app.models.order import (
    PosBill,
    PosBillPayment,
    PosKot,
    PosKotLine,
    PosOrder,
    PosOrderLine,
    PosOrderLineAddon,
)
from app.models.tenant import BusinessOwner
from app.models.venue import VenueArea, VenueTable
from app.schemas.owner.order import (
    AddBillPaymentRequest,
    BillListEntryResponse,
    BillPaymentResponse,
    BillPreviewRequest,
    BillResponse,
    FloorAreaStatus,
    FloorStatusResponse,
    FloorTableStatus,
    KotLineResponse,
    KotResponse,
    OrderCreate,
    OrderLineAddonResponse,
    OrderLineCreate,
    OrderLineResponse,
    OrderLineUpdate,
    OrderResponse,
    OrderTransferTable,
    OrderUpdate,
    SendKotRequest,
    SettleBillRequest,
    PosBillingSettingsResponse,
    SplitBillPreviewBody,
    SplitBillPreviewResponse,
)
from app.services.owner.access import assert_business_operational, get_outlet_for_owner
from app.services.owner.order_counters import next_outlet_counter
from app.services.owner.order_pricing import (
    compute_bill_totals,
    default_tax_percent_for_business,
    line_total,
    money,
    order_subtotal,
    resolve_tax_percent,
    subtotal_from_lines,
)


class OwnerOrderService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def billing_settings(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
    ) -> PosBillingSettingsResponse:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        biz = owner.business
        default_tax = default_tax_percent_for_business(biz.gst_registered, biz.gstin)
        return PosBillingSettingsResponse(
            gst_registered=biz.gst_registered,
            gstin=biz.gstin,
            default_tax_percent=default_tax,
        )

    def _normalize_bill_preview(self, owner: BusinessOwner, payload: BillPreviewRequest) -> BillPreviewRequest:
        biz = owner.business
        tax = resolve_tax_percent(biz.gst_registered, biz.gstin, payload.tax_percent)
        return BillPreviewRequest(
            discount_amount=payload.discount_amount,
            discount_percent=payload.discount_percent,
            tax_percent=tax,
            round_to_rupee=payload.round_to_rupee,
        )

    @staticmethod
    def _discount_inputs_for_recompute(bill: PosBill) -> tuple[Decimal, Decimal]:
        if bill.discount_percent > 0:
            return Decimal("0"), bill.discount_percent
        return bill.discount_amount, Decimal("0")

    async def floor_status(self, owner: BusinessOwner, outlet_id: uuid.UUID) -> FloorStatusResponse:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        areas_result = await self.db.execute(
            select(VenueArea)
            .where(VenueArea.outlet_id == outlet_id)
            .order_by(VenueArea.sort_order, VenueArea.name),
        )
        areas = list(areas_result.scalars().all())
        tables_result = await self.db.execute(
            select(VenueTable).where(VenueTable.outlet_id == outlet_id),
        )
        tables = list(tables_result.scalars().all())
        open_orders_result = await self.db.execute(
            select(PosOrder)
            .where(
                PosOrder.outlet_id == outlet_id,
                PosOrder.status == OrderStatus.OPEN,
                PosOrder.venue_table_id.isnot(None),
            )
            .options(selectinload(PosOrder.lines)),
        )
        open_orders = list(open_orders_result.scalars().all())
        order_by_table: dict[uuid.UUID, PosOrder] = {}
        order_ids: list[uuid.UUID] = []
        for order in open_orders:
            if order.venue_table_id:
                order_by_table[order.venue_table_id] = order
                order_ids.append(order.id)

        latest_kot_at: dict[uuid.UUID, datetime] = {}
        kot_count_by_order: dict[uuid.UUID, int] = {}
        if order_ids:
            kots_result = await self.db.execute(
                select(PosKot)
                .where(PosKot.order_id.in_(order_ids))
                .order_by(PosKot.created_at.desc()),
            )
            for kot in kots_result.scalars().all():
                kot_count_by_order[kot.order_id] = kot_count_by_order.get(kot.order_id, 0) + 1
                if kot.order_id not in latest_kot_at:
                    latest_kot_at[kot.order_id] = kot.created_at

        now = datetime.now(timezone.utc)

        area_payload: list[FloorAreaStatus] = []
        for area in areas:
            area_tables = [t for t in tables if t.area_id == area.id]
            table_rows: list[FloorTableStatus] = []
            for table in sorted(area_tables, key=lambda t: (t.sort_order, t.label)):
                order = order_by_table.get(table.id)
                running = order_subtotal(order) if order else None
                visual = TableVisualState.BLANK
                minutes: Optional[int] = None
                last_kot: Optional[datetime] = None
                kot_count = 0
                if order is not None:
                    kot_count = kot_count_by_order.get(order.id, 0)
                    visual = self._table_visual_state(order, kot_count > 0)
                    last_kot = latest_kot_at.get(order.id)
                    ref = last_kot or order.created_at
                    if ref.tzinfo is None:
                        ref = ref.replace(tzinfo=timezone.utc)
                    minutes = max(0, int((now - ref).total_seconds() // 60))
                table_rows.append(
                    FloorTableStatus(
                        table_id=table.id,
                        area_id=area.id,
                        label=table.label,
                        resource_kind=table.resource_kind.value,
                        is_occupied=order is not None,
                        visual_state=visual,
                        current_order_id=order.id if order else None,
                        order_number=order.order_number if order else None,
                        running_total=running,
                        minutes_elapsed=minutes,
                        last_kot_at=last_kot,
                        kot_count=kot_count,
                    ),
                )
            area_payload.append(
                FloorAreaStatus(area_id=area.id, name=area.name, tables=table_rows),
            )
        return FloorStatusResponse(areas=area_payload)

    async def list_orders(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        order_status: OrderStatus | None = OrderStatus.OPEN,
    ) -> list[OrderResponse]:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        stmt = select(PosOrder).where(PosOrder.outlet_id == outlet_id)
        if order_status is not None:
            stmt = stmt.where(PosOrder.status == order_status)
        stmt = stmt.order_by(PosOrder.created_at.desc())
        result = await self.db.execute(stmt.options(selectinload(PosOrder.lines).selectinload(PosOrderLine.addons)))
        return [self._order_response(o) for o in result.scalars().all()]

    async def create_order(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        payload: OrderCreate,
    ) -> OrderResponse:
        assert_business_operational(owner.business)
        await get_outlet_for_owner(self.db, owner, outlet_id)
        if payload.order_type == OrderType.DINE_IN and payload.venue_table_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="venue_table_id is required for dine-in orders",
            )
        if payload.venue_table_id is not None:
            await self._get_table(owner, outlet_id, payload.venue_table_id)
            existing = await self._open_order_for_table(outlet_id, payload.venue_table_id)
            if existing is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This table already has an open order",
                )
        order_number = await next_outlet_counter(self.db, outlet_id, "order")
        order = PosOrder(
            outlet_id=outlet_id,
            order_type=payload.order_type,
            order_number=order_number,
            venue_table_id=payload.venue_table_id,
            guest_count=payload.guest_count,
            notes=payload.notes,
            opened_by_owner_id=owner.id,
            status=OrderStatus.OPEN,
        )
        self.db.add(order)
        await self.db.commit()
        return await self._fresh_order(owner, outlet_id, order.id)

    async def get_order(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        order_id: uuid.UUID,
    ) -> OrderResponse:
        order = await self._load_order_head(owner, outlet_id, order_id)
        lines = await self._fetch_order_lines(order_id)
        return self._order_response(order, lines)

    async def update_order(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        order_id: uuid.UUID,
        payload: OrderUpdate,
    ) -> OrderResponse:
        assert_business_operational(owner.business)
        order = await self._load_order_head(owner, outlet_id, order_id)
        self._assert_order_open(order)
        if payload.guest_count is not None:
            order.guest_count = payload.guest_count
        if payload.customer_name is not None:
            order.customer_name = payload.customer_name.strip() or None
        if payload.customer_mobile is not None:
            order.customer_mobile = payload.customer_mobile.strip() or None
        if payload.pay_later is not None:
            order.pay_later = payload.pay_later
        if payload.notes is not None:
            order.notes = payload.notes
        await self.db.commit()
        return await self._fresh_order(owner, outlet_id, order_id)

    async def cancel_order(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        order_id: uuid.UUID,
        reason: str | None,
    ) -> OrderResponse:
        assert_business_operational(owner.business)
        order = await self._load_order(owner, outlet_id, order_id)
        self._assert_order_open(order)
        for line in order.lines:
            if line.status != OrderLineStatus.CANCELLED:
                line.status = OrderLineStatus.CANCELLED
        order.status = OrderStatus.CANCELLED
        order.cancelled_at = datetime.now(timezone.utc)
        order.cancel_reason = reason
        await self._void_open_bills(order)
        await self.db.commit()
        return await self._fresh_order(owner, outlet_id, order_id)

    async def transfer_table(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        order_id: uuid.UUID,
        payload: OrderTransferTable,
    ) -> OrderResponse:
        assert_business_operational(owner.business)
        order = await self._load_order(owner, outlet_id, order_id)
        self._assert_order_open(order)
        if order.order_type != OrderType.DINE_IN:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not a dine-in order")
        await self._get_table(owner, outlet_id, payload.venue_table_id)
        if payload.venue_table_id == order.venue_table_id:
            return self._order_response(order)
        other = await self._open_order_for_table(outlet_id, payload.venue_table_id)
        if other is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Target table already has an open order",
            )
        order.venue_table_id = payload.venue_table_id
        await self.db.commit()
        return await self._fresh_order(owner, outlet_id, order_id)

    async def add_line(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        order_id: uuid.UUID,
        payload: OrderLineCreate,
    ) -> OrderResponse:
        assert_business_operational(owner.business)
        order = await self._load_order(owner, outlet_id, order_id)
        self._assert_order_open(order)
        item, variation, addons = await self._resolve_menu_line(
            outlet_id,
            payload.menu_item_id,
            payload.variation_id,
            payload.addon_ids,
        )
        unit_price = variation.price if variation else item.price
        addons_total = sum(a.price for a in addons)
        row = PosOrderLine(
            order_id=order.id,
            menu_item_id=item.id,
            menu_item_variation_id=variation.id if variation else None,
            item_name=item.name,
            variation_name=variation.name if variation else None,
            quantity=payload.quantity,
            unit_price=unit_price,
            addons_total=addons_total,
            line_total=line_total(unit_price, addons_total, payload.quantity),
            notes=payload.notes,
            food_type=item.food_type,
            status=OrderLineStatus.PENDING_KOT,
        )
        for addon in addons:
            row.addons.append(
                PosOrderLineAddon(
                    menu_item_addon_id=addon.id,
                    name=addon.name,
                    price=addon.price,
                ),
            )
        self.db.add(row)
        await self.db.flush()
        await self.db.commit()
        return await self._fresh_order(owner, outlet_id, order_id)

    async def update_line(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        order_id: uuid.UUID,
        line_id: uuid.UUID,
        payload: OrderLineUpdate,
    ) -> OrderResponse:
        assert_business_operational(owner.business)
        order = await self._load_order(owner, outlet_id, order_id)
        self._assert_order_open(order)
        line = self._get_line(order, line_id)
        if line.status != OrderLineStatus.PENDING_KOT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only items not yet sent to kitchen can be edited",
            )
        if payload.quantity is not None:
            line.quantity = payload.quantity
            line.line_total = line_total(line.unit_price, line.addons_total, line.quantity)
        if payload.notes is not None:
            line.notes = payload.notes
        await self.db.commit()
        return await self._fresh_order(owner, outlet_id, order_id)

    async def remove_line(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        order_id: uuid.UUID,
        line_id: uuid.UUID,
    ) -> OrderResponse:
        assert_business_operational(owner.business)
        order = await self._load_order(owner, outlet_id, order_id)
        self._assert_order_open(order)
        line = self._get_line(order, line_id)
        if line.status != OrderLineStatus.PENDING_KOT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove items already sent to kitchen",
            )
        await self.db.delete(line)
        await self.db.commit()
        return await self._fresh_order(owner, outlet_id, order_id)

    async def cancel_line(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        order_id: uuid.UUID,
        line_id: uuid.UUID,
    ) -> OrderResponse:
        assert_business_operational(owner.business)
        order = await self._load_order(owner, outlet_id, order_id)
        self._assert_order_open(order)
        line = self._get_line(order, line_id)
        if line.status == OrderLineStatus.CANCELLED:
            return self._order_response(order)
        line.status = OrderLineStatus.CANCELLED
        await self.db.commit()
        return await self._fresh_order(owner, outlet_id, order_id)

    async def send_kot(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        order_id: uuid.UUID,
        payload: SendKotRequest,
    ) -> KotResponse:
        assert_business_operational(owner.business)
        order = await self._load_order_head(owner, outlet_id, order_id)
        self._assert_order_open(order)
        lines = await self._fetch_order_lines(order_id)
        pending = [line for line in lines if line.status == OrderLineStatus.PENDING_KOT]
        if payload.line_ids:
            allowed = set(payload.line_ids)
            pending = [line for line in pending if line.id in allowed]
        if not pending:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No items pending for KOT")
        kot_number = await next_outlet_counter(self.db, outlet_id, "kot")
        kot = PosKot(
            outlet_id=outlet_id,
            order_id=order.id,
            kot_number=kot_number,
            notes=payload.notes,
            status=KotStatus.ACTIVE,
        )
        for line in pending:
            kot.lines.append(PosKotLine(order_line_id=line.id, quantity=line.quantity))
            line.status = OrderLineStatus.IN_KOT
        self.db.add(kot)
        await self.db.commit()
        return await self.get_kot(owner, outlet_id, kot.id)

    async def list_kots_for_order(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        order_id: uuid.UUID,
    ) -> list[KotResponse]:
        await self._load_order_head(owner, outlet_id, order_id)
        result = await self.db.execute(
            select(PosKot)
            .where(PosKot.order_id == order_id, PosKot.outlet_id == outlet_id)
            .order_by(PosKot.created_at)
            .options(
                selectinload(PosKot.lines).selectinload(PosKotLine.order_line).selectinload(
                    PosOrderLine.addons,
                ),
            ),
        )
        return [self._kot_response(kot) for kot in result.scalars().all()]

    async def get_kot(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        kot_id: uuid.UUID,
    ) -> KotResponse:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        result = await self.db.execute(
            select(PosKot)
            .where(PosKot.id == kot_id, PosKot.outlet_id == outlet_id)
            .options(
                selectinload(PosKot.lines).selectinload(PosKotLine.order_line).selectinload(
                    PosOrderLine.addons,
                ),
            ),
        )
        kot = result.scalar_one_or_none()
        if kot is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="KOT not found")
        return self._kot_response(kot)

    @staticmethod
    def _kot_response(kot: PosKot) -> KotResponse:
        line_payload: list[KotLineResponse] = []
        for kl in kot.lines:
            ol = kl.order_line
            line_payload.append(
                KotLineResponse(
                    id=kl.id,
                    order_line_id=ol.id,
                    quantity=kl.quantity,
                    item_name=ol.item_name,
                    variation_name=ol.variation_name,
                    notes=ol.notes,
                ),
            )
        return KotResponse(
            id=kot.id,
            outlet_id=kot.outlet_id,
            order_id=kot.order_id,
            kot_number=kot.kot_number,
            status=kot.status,
            notes=kot.notes,
            created_at=kot.created_at,
            lines=line_payload,
        )

    async def create_or_refresh_bill(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        order_id: uuid.UUID,
        payload: BillPreviewRequest,
    ) -> BillResponse:
        assert_business_operational(owner.business)
        preview = self._normalize_bill_preview(owner, payload)
        order = await self._load_order_head(owner, outlet_id, order_id)
        self._assert_order_open(order)
        lines = await self._fetch_order_lines(order_id)
        active_lines = [line for line in lines if line.status != OrderLineStatus.CANCELLED]
        if not active_lines:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order has no billable items")
        subtotal = subtotal_from_lines(lines)
        discount, tax_amount, round_off, grand_total, _taxable = compute_bill_totals(
            subtotal,
            preview.discount_amount,
            preview.discount_percent,
            preview.tax_percent,
            preview.round_to_rupee,
        )
        bill = await self._get_open_bill(order.id)
        if bill is None:
            bill_number = await next_outlet_counter(self.db, outlet_id, "bill")
            bill = PosBill(
                outlet_id=outlet_id,
                order_id=order.id,
                bill_number=bill_number,
                subtotal=subtotal,
                discount_amount=discount,
                discount_percent=preview.discount_percent,
                tax_percent=preview.tax_percent,
                tax_amount=tax_amount,
                round_off=round_off,
                grand_total=grand_total,
                status=BillStatus.OPEN,
            )
            self.db.add(bill)
            await self.db.flush()
        else:
            bill.subtotal = subtotal
            bill.discount_amount = discount
            bill.discount_percent = preview.discount_percent
            bill.tax_percent = preview.tax_percent
            bill.tax_amount = tax_amount
            bill.round_off = round_off
            bill.grand_total = grand_total
        await self.db.commit()
        return await self.get_bill(owner, outlet_id, bill.id)

    async def get_bill_for_order(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        order_id: uuid.UUID,
    ) -> BillResponse:
        await self._load_order_head(owner, outlet_id, order_id)
        bill = await self._get_open_bill(order_id)
        if bill is None:
            settled = await self._get_latest_bill(order_id)
            if settled is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No bill for this order")
            bill = settled
        return await self.get_bill(owner, outlet_id, bill.id)

    async def get_bill(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        bill_id: uuid.UUID,
    ) -> BillResponse:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        result = await self.db.execute(
            select(PosBill)
            .where(PosBill.id == bill_id, PosBill.outlet_id == outlet_id)
            .options(selectinload(PosBill.payments)),
        )
        bill = result.scalar_one_or_none()
        if bill is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
        return self._bill_response(bill)

    async def list_bills(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        bill_status: BillStatus | None = BillStatus.SETTLED,
        limit: int = 200,
    ) -> list[BillListEntryResponse]:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        stmt = (
            select(PosBill, PosOrder, VenueTable)
            .join(PosOrder, PosBill.order_id == PosOrder.id)
            .outerjoin(VenueTable, PosOrder.venue_table_id == VenueTable.id)
            .where(PosBill.outlet_id == outlet_id)
            .order_by(PosBill.created_at.desc())
            .limit(min(limit, 500))
            .options(selectinload(PosBill.payments))
        )
        if bill_status is not None:
            stmt = stmt.where(PosBill.status == bill_status)
        result = await self.db.execute(stmt)
        entries: list[BillListEntryResponse] = []
        for bill, order, table in result.all():
            base = self._bill_response(bill)
            entries.append(
                BillListEntryResponse(
                    **base.model_dump(),
                    order_number=order.order_number,
                    settled_at=order.settled_at,
                    created_at=bill.created_at,
                    table_label=table.label if table else None,
                    customer_name=order.customer_name,
                ),
            )
        return entries

    async def add_bill_payment(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        bill_id: uuid.UUID,
        payload: AddBillPaymentRequest,
    ) -> BillResponse:
        assert_business_operational(owner.business)
        bill = await self._load_bill(owner, outlet_id, bill_id)
        if bill.status != BillStatus.OPEN:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bill is not open")
        order = await self._load_order_head(owner, outlet_id, bill.order_id)
        self._assert_order_open(order)
        disc_amt, disc_pct = self._discount_inputs_for_recompute(bill)
        await self._refresh_bill_amounts(bill, bill.order_id, disc_amt, disc_pct, bill.tax_percent)
        paid_before = sum(p.amount for p in bill.payments)
        paid_after = paid_before + payload.amount
        if money(paid_after) > money(bill.grand_total):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment exceeds balance due",
            )
        bill.payments.append(
            PosBillPayment(
                method=payload.method,
                amount=money(payload.amount),
                reference=payload.reference,
            ),
        )
        paid = paid_after
        if money(paid) == money(bill.grand_total):
            bill.status = BillStatus.SETTLED
            order.status = OrderStatus.SETTLED
            order.settled_at = datetime.now(timezone.utc)
        await self.db.commit()
        return await self.get_bill(owner, outlet_id, bill.id)

    async def split_bill_preview(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        order_id: uuid.UUID,
        payload: SplitBillPreviewBody,
    ) -> SplitBillPreviewResponse:
        bill = await self.create_or_refresh_bill(owner, outlet_id, order_id, payload)
        per = money(bill.grand_total / Decimal(payload.parts))
        return SplitBillPreviewResponse(
            parts=payload.parts,
            grand_total=bill.grand_total,
            amount_per_part=per,
        )

    async def settle_bill(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        bill_id: uuid.UUID,
        payload: SettleBillRequest,
    ) -> BillResponse:
        assert_business_operational(owner.business)
        preview = self._normalize_bill_preview(owner, payload)
        bill = await self._load_bill(owner, outlet_id, bill_id)
        if bill.status != BillStatus.OPEN:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bill is already settled")
        order = await self._load_order_head(owner, outlet_id, bill.order_id)
        self._assert_order_open(order)
        lines = await self._fetch_order_lines(bill.order_id)
        subtotal = subtotal_from_lines(lines)
        discount, tax_amount, round_off, grand_total, _taxable = compute_bill_totals(
            subtotal,
            preview.discount_amount,
            preview.discount_percent,
            preview.tax_percent,
            preview.round_to_rupee,
        )
        bill.subtotal = subtotal
        bill.discount_amount = discount
        bill.discount_percent = preview.discount_percent
        bill.tax_percent = preview.tax_percent
        bill.tax_amount = tax_amount
        bill.round_off = round_off
        bill.grand_total = grand_total
        existing_paid = sum((p.amount for p in bill.payments), Decimal("0"))
        new_paid = sum((p.amount for p in payload.payments), Decimal("0"))
        total_paid = existing_paid + new_paid
        if money(total_paid) != money(bill.grand_total):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Payments ({total_paid}) must equal grand total ({bill.grand_total})",
            )
        if not payload.payments and money(existing_paid) == money(bill.grand_total):
            bill.status = BillStatus.SETTLED
            order.status = OrderStatus.SETTLED
            order.settled_at = datetime.now(timezone.utc)
            await self.db.commit()
            return await self.get_bill(owner, outlet_id, bill.id)
        for payment in payload.payments:
            bill.payments.append(
                PosBillPayment(
                    method=payment.method,
                    amount=money(payment.amount),
                    reference=payment.reference,
                ),
            )
        bill.status = BillStatus.SETTLED
        order.status = OrderStatus.SETTLED
        order.settled_at = datetime.now(timezone.utc)
        await self.db.commit()
        return await self.get_bill(owner, outlet_id, bill.id)

    async def _refresh_bill_amounts(
        self,
        bill: PosBill,
        order_id: uuid.UUID,
        discount_amount: Decimal,
        discount_percent: Decimal,
        tax_percent: Decimal,
    ) -> None:
        lines = await self._fetch_order_lines(order_id)
        subtotal = subtotal_from_lines(lines)
        discount, tax_amount, round_off, grand_total, _taxable = compute_bill_totals(
            subtotal,
            discount_amount,
            discount_percent,
            tax_percent,
            True,
        )
        bill.subtotal = subtotal
        bill.discount_amount = discount
        bill.discount_percent = discount_percent
        bill.tax_percent = tax_percent
        bill.tax_amount = tax_amount
        bill.round_off = round_off
        bill.grand_total = grand_total

    def _bill_response(self, bill: PosBill) -> BillResponse:
        paid = sum((p.amount for p in bill.payments), Decimal("0"))
        payments_out = [
            BillPaymentResponse(
                id=p.id,
                method=p.method,
                amount=p.amount,
                reference=p.reference,
            )
            for p in bill.payments
        ]
        return BillResponse(
            id=bill.id,
            outlet_id=bill.outlet_id,
            order_id=bill.order_id,
            bill_number=bill.bill_number,
            subtotal=bill.subtotal,
            discount_amount=bill.discount_amount,
            discount_percent=bill.discount_percent,
            tax_percent=bill.tax_percent,
            tax_amount=bill.tax_amount,
            round_off=bill.round_off,
            grand_total=bill.grand_total,
            amount_paid=money(paid),
            balance_due=money(bill.grand_total - paid),
            status=bill.status,
            payments=payments_out,
        )

    async def _resolve_menu_line(
        self,
        outlet_id: uuid.UUID,
        menu_item_id: uuid.UUID,
        variation_id: uuid.UUID | None,
        addon_ids: list[uuid.UUID],
    ) -> tuple[MenuItem, MenuItemVariation | None, list[MenuItemAddon]]:
        result = await self.db.execute(
            select(MenuItem)
            .where(MenuItem.id == menu_item_id, MenuItem.outlet_id == outlet_id)
            .options(
                selectinload(MenuItem.variations),
                selectinload(MenuItem.addons),
            ),
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")
        if not item.is_available:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Item is out of stock")
        variation: MenuItemVariation | None = None
        if variation_id is not None:
            variation = next((v for v in item.variations if v.id == variation_id), None)
            if variation is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid variation")
        elif item.variations:
            defaults = [v for v in item.variations if v.is_default]
            variation = defaults[0] if defaults else item.variations[0]
        addons: list[MenuItemAddon] = []
        if addon_ids:
            addon_map = {a.id: a for a in item.addons if a.is_available}
            for aid in addon_ids:
                addon = addon_map.get(aid)
                if addon is None:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid add-on")
                addons.append(addon)
        return item, variation, addons

    async def _open_order_for_table(
        self,
        outlet_id: uuid.UUID,
        table_id: uuid.UUID,
    ) -> PosOrder | None:
        result = await self.db.execute(
            select(PosOrder).where(
                PosOrder.outlet_id == outlet_id,
                PosOrder.venue_table_id == table_id,
                PosOrder.status == OrderStatus.OPEN,
            ),
        )
        return result.scalar_one_or_none()

    async def _load_order(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        order_id: uuid.UUID,
    ) -> PosOrder:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        result = await self.db.execute(
            select(PosOrder)
            .where(PosOrder.id == order_id, PosOrder.outlet_id == outlet_id)
            .options(selectinload(PosOrder.lines).selectinload(PosOrderLine.addons))
            .execution_options(populate_existing=True),
        )
        order = result.scalar_one_or_none()
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        return order

    async def _load_bill(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        bill_id: uuid.UUID,
    ) -> PosBill:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        result = await self.db.execute(
            select(PosBill)
            .where(PosBill.id == bill_id, PosBill.outlet_id == outlet_id)
            .options(selectinload(PosBill.payments)),
        )
        bill = result.scalar_one_or_none()
        if bill is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
        return bill

    async def _get_table(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        table_id: uuid.UUID,
    ) -> VenueTable:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        result = await self.db.execute(
            select(VenueTable).where(
                VenueTable.id == table_id,
                VenueTable.outlet_id == outlet_id,
            ),
        )
        table = result.scalar_one_or_none()
        if table is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")
        return table

    async def _get_open_bill(self, order_id: uuid.UUID) -> PosBill | None:
        result = await self.db.execute(
            select(PosBill).where(
                PosBill.order_id == order_id,
                PosBill.status == BillStatus.OPEN,
            ),
        )
        return result.scalar_one_or_none()

    async def _get_latest_bill(self, order_id: uuid.UUID) -> PosBill | None:
        result = await self.db.execute(
            select(PosBill)
            .where(PosBill.order_id == order_id)
            .order_by(PosBill.created_at.desc())
            .limit(1),
        )
        return result.scalar_one_or_none()

    async def _void_open_bills(self, order: PosOrder) -> None:
        result = await self.db.execute(
            select(PosBill).where(
                PosBill.order_id == order.id,
                PosBill.status == BillStatus.OPEN,
            ),
        )
        for bill in result.scalars().all():
            bill.status = BillStatus.VOID

    def _get_line(self, order: PosOrder, line_id: uuid.UUID) -> PosOrderLine:
        for line in order.lines:
            if line.id == line_id:
                return line
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order line not found")

    def _assert_order_open(self, order: PosOrder) -> None:
        if order.status != OrderStatus.OPEN:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order is not open")

    @staticmethod
    def _table_visual_state(order: PosOrder, has_kot_sent: bool) -> TableVisualState:
        active = [line for line in order.lines if line.status != OrderLineStatus.CANCELLED]
        if not active:
            return TableVisualState.RUNNING
        in_kitchen = any(
            line.status in (OrderLineStatus.IN_KOT, OrderLineStatus.SERVED) for line in active
        )
        if has_kot_sent or in_kitchen:
            return TableVisualState.RUNNING_KOT
        return TableVisualState.RUNNING

    async def _fresh_order(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        order_id: uuid.UUID,
    ) -> OrderResponse:
        return await self.get_order(owner, outlet_id, order_id)

    async def _load_order_head(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        order_id: uuid.UUID,
    ) -> PosOrder:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        result = await self.db.execute(
            select(PosOrder).where(PosOrder.id == order_id, PosOrder.outlet_id == outlet_id),
        )
        order = result.scalar_one_or_none()
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        return order

    async def _fetch_order_lines(self, order_id: uuid.UUID) -> list[PosOrderLine]:
        result = await self.db.execute(
            select(PosOrderLine)
            .where(PosOrderLine.order_id == order_id)
            .options(selectinload(PosOrderLine.addons))
            .order_by(PosOrderLine.created_at.asc()),
        )
        return list(result.scalars().all())

    def _order_response(
        self,
        order: PosOrder,
        lines: list[PosOrderLine] | None = None,
    ) -> OrderResponse:
        source = lines if lines is not None else order.lines
        lines_out: list[OrderLineResponse] = []
        subtotal = Decimal("0")
        for line in source:
            lr = OrderLineResponse.model_validate(line)
            lr.addons = [OrderLineAddonResponse.model_validate(a) for a in line.addons]
            lines_out.append(lr)
            if line.status != OrderLineStatus.CANCELLED:
                subtotal += line.line_total
        return OrderResponse(
            id=order.id,
            outlet_id=order.outlet_id,
            order_type=order.order_type,
            order_number=order.order_number,
            venue_table_id=order.venue_table_id,
            status=order.status,
            guest_count=order.guest_count,
            customer_name=order.customer_name,
            customer_mobile=order.customer_mobile,
            pay_later=order.pay_later,
            notes=order.notes,
            created_at=order.created_at,
            settled_at=order.settled_at,
            lines=lines_out,
            running_subtotal=money(subtotal),
        )
