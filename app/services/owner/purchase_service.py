from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inventory import InventoryItem, InventoryTransaction
from app.models.purchase import PurchaseInvoice, PurchaseInvoiceLine, PurchasePayment
from app.models.tenant import BusinessOwner
from app.schemas.owner.purchase import (
    PurchaseInvoiceCreate,
    PurchaseInvoiceDetail,
    PurchaseInvoiceSummary,
    PurchaseInvoiceUpdate,
    PurchaseLineResponse,
    PurchaseListResponse,
    PurchaseListTotals,
    PurchasePaymentCreate,
    PurchasePaymentResponse,
)
from app.services.owner.access import assert_business_operational, get_outlet_for_owner
from app.services.owner.order_pricing import money
from app.services.owner.sales_analytics_helpers import OUTLET_TZ

STOCK_QTY = Decimal("0.001")


def _qty(value: Decimal | int | float | str | None) -> Decimal:
    if value is None:
        value = Decimal("0")
    elif not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(STOCK_QTY)


def _payment_status(total: Decimal, paid: Decimal) -> str:
    if paid <= 0:
        return "unpaid"
    if paid >= total:
        return "paid"
    return "partial"


class OwnerPurchaseService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def outlet_today() -> date:
        return datetime.now(OUTLET_TZ).date()

    # ---------- responses ----------

    def _summary(
        self,
        inv: PurchaseInvoice,
        line_count: int,
        created_by_name: str | None,
    ) -> PurchaseInvoiceSummary:
        total = money(inv.total_inr)
        paid = money(inv.paid_inr)
        return PurchaseInvoiceSummary(
            id=inv.id,
            vendor_name=inv.vendor_name,
            invoice_number=inv.invoice_number,
            invoice_date=inv.invoice_date,
            po_reference=inv.po_reference,
            total_inr=total,
            paid_inr=paid,
            balance_inr=money(max(total - paid, Decimal("0"))),
            tax_inr=money(inv.tax_inr),
            payment_status=inv.payment_status,
            status=inv.status,
            stock_applied=inv.stock_applied,
            line_count=line_count,
            created_by_name=created_by_name,
            created_at=inv.created_at,
        )

    def _detail(self, inv: PurchaseInvoice, created_by_name: str | None) -> PurchaseInvoiceDetail:
        base = self._summary(inv, len(inv.lines), created_by_name)
        return PurchaseInvoiceDetail(
            **base.model_dump(),
            outlet_id=inv.outlet_id,
            vendor_phone=inv.vendor_phone,
            vendor_gstin=inv.vendor_gstin,
            subtotal_inr=money(inv.subtotal_inr),
            discount_inr=money(inv.discount_inr),
            other_charges_inr=money(inv.other_charges_inr),
            payment_mode=inv.payment_mode,
            notes=inv.notes,
            lines=[PurchaseLineResponse.model_validate(line) for line in inv.lines],
            payments=[PurchasePaymentResponse.model_validate(p) for p in inv.payments],
        )

    async def _owner_names(self, owner_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        ids = [i for i in owner_ids if i is not None]
        if not ids:
            return {}
        result = await self.db.execute(
            select(BusinessOwner.id, BusinessOwner.full_name).where(BusinessOwner.id.in_(ids)),
        )
        return {row[0]: row[1] for row in result.all()}

    # ---------- list ----------

    async def list_invoices(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        from_date: date | None,
        to_date: date | None,
        vendor: str | None,
        invoice_number: str | None,
        payment_status: str | None,
    ) -> PurchaseListResponse:
        await get_outlet_for_owner(self.db, owner, outlet_id)

        stmt = select(PurchaseInvoice).where(PurchaseInvoice.outlet_id == outlet_id)
        if from_date is not None:
            stmt = stmt.where(PurchaseInvoice.invoice_date >= from_date)
        if to_date is not None:
            stmt = stmt.where(PurchaseInvoice.invoice_date <= to_date)
        if vendor:
            stmt = stmt.where(PurchaseInvoice.vendor_name.ilike(f"%{vendor.strip()}%"))
        if invoice_number:
            stmt = stmt.where(PurchaseInvoice.invoice_number.ilike(f"%{invoice_number.strip()}%"))
        if payment_status and payment_status != "all":
            stmt = stmt.where(PurchaseInvoice.payment_status == payment_status)
        stmt = stmt.order_by(PurchaseInvoice.invoice_date.desc(), PurchaseInvoice.created_at.desc())

        result = await self.db.execute(stmt)
        invoices = list(result.scalars().all())
        ids = [inv.id for inv in invoices]

        line_counts: dict[uuid.UUID, int] = {}
        if ids:
            count_result = await self.db.execute(
                select(PurchaseInvoiceLine.invoice_id, func.count(PurchaseInvoiceLine.id))
                .where(PurchaseInvoiceLine.invoice_id.in_(ids))
                .group_by(PurchaseInvoiceLine.invoice_id),
            )
            line_counts = {row[0]: int(row[1]) for row in count_result.all()}

        names = await self._owner_names({inv.created_by_owner_id for inv in invoices if inv.created_by_owner_id})

        total = money(sum((money(i.total_inr) for i in invoices), Decimal("0")))
        paid = money(sum((money(i.paid_inr) for i in invoices), Decimal("0")))
        tax = money(sum((money(i.tax_inr) for i in invoices), Decimal("0")))

        vendor_result = await self.db.execute(
            select(PurchaseInvoice.vendor_name)
            .where(PurchaseInvoice.outlet_id == outlet_id)
            .distinct()
            .order_by(PurchaseInvoice.vendor_name),
        )
        vendors = [row[0] for row in vendor_result.all()]

        return PurchaseListResponse(
            from_date=from_date,
            to_date=to_date,
            totals=PurchaseListTotals(
                invoice_count=len(invoices),
                total_inr=total,
                paid_inr=paid,
                outstanding_inr=money(max(total - paid, Decimal("0"))),
                tax_inr=tax,
            ),
            vendors=vendors,
            invoices=[
                self._summary(
                    inv,
                    line_counts.get(inv.id, 0),
                    names.get(inv.created_by_owner_id) if inv.created_by_owner_id else None,
                )
                for inv in invoices
            ],
        )

    # ---------- detail ----------

    async def _get_invoice(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        invoice_id: uuid.UUID,
    ) -> PurchaseInvoice:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        result = await self.db.execute(
            select(PurchaseInvoice)
            .where(PurchaseInvoice.id == invoice_id, PurchaseInvoice.outlet_id == outlet_id)
            .options(selectinload(PurchaseInvoice.lines), selectinload(PurchaseInvoice.payments)),
        )
        inv = result.scalar_one_or_none()
        if inv is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase invoice not found")
        return inv

    async def get_invoice(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        invoice_id: uuid.UUID,
    ) -> PurchaseInvoiceDetail:
        inv = await self._get_invoice(owner, outlet_id, invoice_id)
        names = await self._owner_names({inv.created_by_owner_id} if inv.created_by_owner_id else set())
        return self._detail(inv, names.get(inv.created_by_owner_id) if inv.created_by_owner_id else None)

    # ---------- create ----------

    async def create_invoice(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        payload: PurchaseInvoiceCreate,
    ) -> PurchaseInvoiceDetail:
        assert_business_operational(owner.business)
        await get_outlet_for_owner(self.db, owner, outlet_id)

        raw_ids = {line.inventory_item_id for line in payload.lines if line.inventory_item_id}
        raw_by_id: dict[uuid.UUID, InventoryItem] = {}
        if raw_ids:
            raw_result = await self.db.execute(
                select(InventoryItem).where(
                    InventoryItem.id.in_(raw_ids),
                    InventoryItem.outlet_id == outlet_id,
                ),
            )
            raw_by_id = {item.id: item for item in raw_result.scalars().all()}
            missing = raw_ids - set(raw_by_id.keys())
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="One or more raw materials on this bill do not belong to this outlet",
                )

        subtotal = Decimal("0")
        tax_total = Decimal("0")
        line_models: list[PurchaseInvoiceLine] = []
        for idx, line in enumerate(payload.lines):
            qty = _qty(line.quantity)
            base = money(qty * money(line.unit_price_inr))
            tax = money(base * money(line.tax_percent) / Decimal("100"))
            line_total = money(base + tax)
            subtotal += base
            tax_total += tax
            material = raw_by_id.get(line.inventory_item_id) if line.inventory_item_id else None
            line_models.append(
                PurchaseInvoiceLine(
                    inventory_item_id=material.id if material else None,
                    item_name=(material.name if material else line.item_name).strip(),
                    quantity=qty,
                    unit=(material.unit if material else line.unit).strip() or "pcs",
                    unit_price_inr=money(line.unit_price_inr),
                    tax_percent=money(line.tax_percent),
                    line_total_inr=line_total,
                    sort_order=idx,
                ),
            )

        discount = money(payload.discount_inr)
        other = money(payload.other_charges_inr)
        total = money(subtotal + tax_total - discount + other)
        if total < 0:
            raise HTTPException(status_code=400, detail="Discount cannot exceed the bill amount")
        paid = money(payload.paid_inr)
        if paid > total:
            raise HTTPException(status_code=400, detail="Paid amount cannot exceed the bill total")

        inv = PurchaseInvoice(
            outlet_id=outlet_id,
            vendor_name=payload.vendor_name.strip(),
            vendor_phone=(payload.vendor_phone or "").strip() or None,
            vendor_gstin=(payload.vendor_gstin or "").strip().upper() or None,
            invoice_number=(payload.invoice_number or "").strip() or None,
            invoice_date=payload.invoice_date,
            po_reference=(payload.po_reference or "").strip() or None,
            subtotal_inr=money(subtotal),
            tax_inr=money(tax_total),
            discount_inr=discount,
            other_charges_inr=other,
            total_inr=total,
            paid_inr=paid,
            payment_mode=payload.payment_mode if paid > 0 else None,
            payment_status=_payment_status(total, paid),
            status="saved",
            stock_applied=False,
            notes=(payload.notes or "").strip() or None,
            created_by_owner_id=owner.id,
        )
        inv.lines = line_models
        self.db.add(inv)
        await self.db.flush()

        if paid > 0:
            self.db.add(
                PurchasePayment(
                    invoice_id=inv.id,
                    amount_inr=paid,
                    payment_mode=payload.payment_mode or "cash",
                    paid_on=payload.invoice_date,
                    reference=None,
                    notes="Paid with bill",
                    created_by_owner_id=owner.id,
                ),
            )

        if payload.apply_stock:
            self._apply_stock(inv, raw_by_id)

        await self.db.commit()
        return await self.get_invoice(owner, outlet_id, inv.id)

    def _apply_stock(self, inv: PurchaseInvoice, raw_by_id: dict[uuid.UUID, InventoryItem]) -> None:
        touched = False
        for line in inv.lines:
            if not line.inventory_item_id:
                continue
            material = raw_by_id.get(line.inventory_item_id)
            if material is None:
                continue
            qty = _qty(line.quantity)
            material.current_stock = _qty(_qty(material.current_stock) + qty)
            if money(line.unit_price_inr) > 0:
                material.cost_per_unit = money(line.unit_price_inr)
            label = inv.invoice_number or inv.vendor_name
            self.db.add(
                InventoryTransaction(
                    inventory_item_id=material.id,
                    outlet_id=inv.outlet_id,
                    delta=qty,
                    reason="purchase",
                    notes=f"Purchase bill {label}",
                ),
            )
            touched = True
        inv.stock_applied = touched

    async def apply_stock(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        invoice_id: uuid.UUID,
    ) -> PurchaseInvoiceDetail:
        assert_business_operational(owner.business)
        inv = await self._get_invoice(owner, outlet_id, invoice_id)
        if inv.stock_applied:
            raise HTTPException(status_code=409, detail="Stock already added for this bill")
        raw_ids = {line.inventory_item_id for line in inv.lines if line.inventory_item_id}
        raw_by_id: dict[uuid.UUID, InventoryItem] = {}
        if raw_ids:
            result = await self.db.execute(
                select(InventoryItem).where(InventoryItem.id.in_(raw_ids)),
            )
            raw_by_id = {item.id: item for item in result.scalars().all()}
        if not raw_by_id:
            raise HTTPException(
                status_code=400,
                detail="No lines on this bill are linked to a raw material",
            )
        self._apply_stock(inv, raw_by_id)
        await self.db.commit()
        return await self.get_invoice(owner, outlet_id, inv.id)

    # ---------- update / delete ----------

    async def update_invoice(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        invoice_id: uuid.UUID,
        payload: PurchaseInvoiceUpdate,
    ) -> PurchaseInvoiceDetail:
        assert_business_operational(owner.business)
        inv = await self._get_invoice(owner, outlet_id, invoice_id)
        if payload.vendor_name is not None:
            inv.vendor_name = payload.vendor_name.strip() or inv.vendor_name
        if payload.vendor_phone is not None:
            inv.vendor_phone = payload.vendor_phone.strip() or None
        if payload.vendor_gstin is not None:
            inv.vendor_gstin = payload.vendor_gstin.strip().upper() or None
        if payload.invoice_number is not None:
            inv.invoice_number = payload.invoice_number.strip() or None
        if payload.invoice_date is not None:
            inv.invoice_date = payload.invoice_date
        if payload.po_reference is not None:
            inv.po_reference = payload.po_reference.strip() or None
        if payload.notes is not None:
            inv.notes = payload.notes.strip() or None
        await self.db.commit()
        return await self.get_invoice(owner, outlet_id, inv.id)

    async def delete_invoice(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        invoice_id: uuid.UUID,
    ) -> None:
        assert_business_operational(owner.business)
        inv = await self._get_invoice(owner, outlet_id, invoice_id)
        if inv.stock_applied:
            # Reverse the stock-in so the ledger stays honest.
            for line in inv.lines:
                if not line.inventory_item_id:
                    continue
                material = await self.db.get(InventoryItem, line.inventory_item_id)
                if material is None:
                    continue
                qty = _qty(line.quantity)
                material.current_stock = _qty(max(_qty(material.current_stock) - qty, Decimal("0")))
                self.db.add(
                    InventoryTransaction(
                        inventory_item_id=material.id,
                        outlet_id=outlet_id,
                        delta=-qty,
                        reason="adjustment",
                        notes=f"Purchase bill {inv.invoice_number or inv.vendor_name} deleted",
                    ),
                )
        await self.db.delete(inv)
        await self.db.commit()

    # ---------- payments ----------

    async def add_payment(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        invoice_id: uuid.UUID,
        payload: PurchasePaymentCreate,
    ) -> PurchaseInvoiceDetail:
        assert_business_operational(owner.business)
        inv = await self._get_invoice(owner, outlet_id, invoice_id)
        amount = money(payload.amount_inr)
        total = money(inv.total_inr)
        paid = money(inv.paid_inr)
        if paid + amount > total:
            raise HTTPException(
                status_code=400,
                detail=f"Payment exceeds balance (₹{money(total - paid)} left)",
            )
        self.db.add(
            PurchasePayment(
                invoice_id=inv.id,
                amount_inr=amount,
                payment_mode=payload.payment_mode,
                paid_on=payload.paid_on or self.outlet_today(),
                reference=(payload.reference or "").strip() or None,
                notes=(payload.notes or "").strip() or None,
                created_by_owner_id=owner.id,
            ),
        )
        inv.paid_inr = money(paid + amount)
        inv.payment_mode = payload.payment_mode
        inv.payment_status = _payment_status(total, inv.paid_inr)
        await self.db.commit()
        return await self.get_invoice(owner, outlet_id, inv.id)
