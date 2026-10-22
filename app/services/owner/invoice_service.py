from __future__ import annotations

import html
import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.compliance import BusinessPosSettings
from app.models.order import PosBill, PosOrder, PosOrderLine
from app.models.tenant import Business, BusinessOwner
from app.services.owner.access import get_outlet_for_owner
from app.services.owner.order_counters import next_outlet_counter
from app.services.owner.order_pricing import money


class InvoiceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def assign_invoice_on_settle(self, bill: PosBill, business_id: uuid.UUID) -> None:
        if bill.invoice_code:
            return
        settings = await self._pos_settings(business_id)
        serial = await next_outlet_counter(self.db, bill.outlet_id, "invoice")
        prefix = (settings.invoice_prefix or "INV").strip()
        bill.invoice_number = serial
        bill.invoice_code = f"{prefix}-{serial:05d}"

    async def _pos_settings(self, business_id: uuid.UUID) -> BusinessPosSettings:
        result = await self.db.execute(
            select(BusinessPosSettings).where(BusinessPosSettings.business_id == business_id),
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = BusinessPosSettings(business_id=business_id)
            self.db.add(row)
            await self.db.flush()
        return row

    async def render_invoice_html(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        bill_id: uuid.UUID,
    ) -> str:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        result = await self.db.execute(
            select(PosBill)
            .where(PosBill.id == bill_id, PosBill.outlet_id == outlet_id)
            .options(selectinload(PosBill.payments)),
        )
        bill = result.scalar_one_or_none()
        if bill is None:
            raise HTTPException(status_code=404, detail="Bill not found")
        order = await self.db.get(PosOrder, bill.order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        lines_result = await self.db.execute(
            select(PosOrderLine).where(PosOrderLine.order_id == order.id),
        )
        lines = list(lines_result.scalars().all())
        business = await self.db.get(Business, owner.business_id)
        pos = await self._pos_settings(owner.business_id)
        name = pos.trading_name or business.legal_name if business else "Outlet"
        addr = pos.registered_address or ""
        gstin = business.gstin if business and business.gst_registered else ""
        fssai = business.fssai if business else ""
        inv = bill.invoice_code or f"BILL-{bill.bill_number}"
        rows = ""
        for line in lines:
            if line.status.value == "cancelled":
                continue
            rows += (
                f"<tr><td>{html.escape(line.item_name)}</td>"
                f"<td class='num'>{line.quantity}</td>"
                f"<td class='num'>{money(line.unit_price)}</td>"
                f"<td class='num'>{money(line.line_total)}</td></tr>"
            )
        payments = "".join(
            f"<li>{html.escape(p.method.value)}: ₹{money(p.amount)}</li>" for p in bill.payments
        )
        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><title>Tax Invoice {html.escape(inv)}</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 720px; margin: 1rem auto; color: #111; }}
h1 {{ font-size: 1.25rem; margin: 0 0 0.25rem; }}
.meta {{ font-size: 0.85rem; color: #444; margin-bottom: 1rem; }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
th, td {{ border-bottom: 1px solid #ddd; padding: 0.35rem 0.25rem; text-align: left; }}
.num {{ text-align: right; }}
.totals {{ margin-top: 1rem; width: 100%; max-width: 320px; margin-left: auto; }}
.totals dt {{ float: left; clear: left; }}
.totals dd {{ float: right; margin: 0 0 0.35rem; }}
.footer {{ margin-top: 1.5rem; font-size: 0.8rem; color: #666; }}
@media print {{ body {{ margin: 0; }} }}
</style></head><body>
<h1>{html.escape(name)}</h1>
<div class="meta">
  <div>Tax Invoice: <strong>{html.escape(inv)}</strong> · Bill #{bill.bill_number}</div>
  {f"<div>GSTIN: {html.escape(gstin)}</div>" if gstin else ""}
  {f"<div>FSSAI: {html.escape(fssai)}</div>" if fssai else ""}
  {f"<div>{html.escape(addr)}</div>" if addr else ""}
  <div>Table: {html.escape(order.table_label_snapshot or "—")}</div>
</div>
<table><thead><tr><th>Item</th><th class="num">Qty</th><th class="num">Rate</th><th class="num">Amount</th></tr></thead>
<tbody>{rows}</tbody></table>
<dl class="totals">
  <dt>Subtotal</dt><dd>₹{money(bill.subtotal)}</dd>
  <dt>Discount</dt><dd>−₹{money(bill.discount_amount)}</dd>
  <dt>CGST</dt><dd>₹{money(bill.cgst_amount)}</dd>
  <dt>SGST</dt><dd>₹{money(bill.sgst_amount)}</dd>
  <dt><strong>Grand total</strong></dt><dd><strong>₹{money(bill.grand_total)}</strong></dd>
  {f"<dt>Refunded</dt><dd>−₹{money(bill.refunded_total)}</dd>" if bill.refunded_total > 0 else ""}
</dl>
<ul>{payments}</ul>
<p class="footer">Computer-generated invoice · KhataBabu</p>
</body></html>"""
