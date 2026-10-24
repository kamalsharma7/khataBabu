from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import OrderType
from app.models.menu import MenuItem
from app.models.tax import OutletTaxProfile, OutletTaxProfileItem
from app.models.tenant import BusinessOwner
from app.schemas.owner.tax import (
    TaxCatalogResponse,
    TaxPreviewLine,
    TaxPreviewRequest,
    TaxPreviewResponse,
    TaxProfileCreate,
    TaxProfileResponse,
    TaxProfileUpdate,
)
from app.services.owner.access import get_outlet_for_owner
from app.services.owner.order_pricing import money
from app.services.owner.tax_engine import (
    GST_SLABS,
    applies_to_order,
    compute_from_profiles,
    default_titles,
    fill_gst_split,
    guest_pays,
)

GST_CATALOG = (
    ("gst_5", Decimal("5"), 0),
    ("gst_18", Decimal("18"), 1),
    ("gst_40", Decimal("40"), 2),
    ("igst", Decimal("5"), 3),
)


def _fill_rates(scheme: str, gst_slab: Optional[str], rate: Decimal) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    if scheme == "gst":
        slab = gst_slab or "gst_5"
        if slab in GST_SLABS and slab != "custom":
            rate = GST_SLABS[slab] if slab != "igst" else rate
        cgst, sgst, igst = fill_gst_split(scheme, slab, rate)
        return money(rate), cgst, sgst, igst
    return money(rate), Decimal("0"), Decimal("0"), Decimal("0")


class OwnerTaxService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_profiles(self, owner: BusinessOwner, outlet_id: uuid.UUID) -> list[TaxProfileResponse]:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        await self._ensure_gst_catalog(outlet_id)
        rows = await self._all(outlet_id)
        return [self._to_response(r) for r in rows]

    async def catalog(self, owner: BusinessOwner, outlet_id: uuid.UUID) -> TaxCatalogResponse:
        profiles = await self.list_profiles(owner, outlet_id)
        active = [p for p in profiles if p.is_active and money(p.rate_percent) > 0]
        rate = money(sum((money(p.rate_percent) for p in active), Decimal("0")))
        method = active[0].method if active else "forward"
        label = " + ".join(p.title for p in active) if active else None
        return TaxCatalogResponse(
            profiles=profiles,
            tax_enabled=bool(active),
            default_tax_percent=rate,
            default_method=method,
            tax_label=label,
        )

    async def create(self, owner: BusinessOwner, outlet_id: uuid.UUID, payload: TaxProfileCreate) -> TaxProfileResponse:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        row = OutletTaxProfile(outlet_id=outlet_id, sort_order=await self._next_sort(outlet_id))
        self._apply_create(row, payload)
        self.db.add(row)
        await self.db.flush()
        await self._replace_items(row, payload.menu_item_ids, payload.scheme)
        if payload.scheme == "gst" and payload.is_active:
            await self._deactivate_other_gst(outlet_id, row.id)
        await self.db.commit()
        await self.db.refresh(row)
        return self._to_response(row)

    async def update(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        profile_id: uuid.UUID,
        payload: TaxProfileUpdate,
    ) -> TaxProfileResponse:
        row = await self._get(owner, outlet_id, profile_id)
        data = payload.model_dump(exclude_unset=True)
        item_ids = data.pop("menu_item_ids", None)
        scheme = data.get("scheme", row.scheme)
        gst_slab = data.get("gst_slab", row.gst_slab)
        rate = data.get("rate_percent", row.rate_percent)
        if any(k in data for k in ("scheme", "gst_slab", "rate_percent")):
            rate, cgst, sgst, igst = _fill_rates(scheme, gst_slab, rate)
            data["rate_percent"] = rate
            if "cgst_percent" not in data:
                data["cgst_percent"] = cgst
            if "sgst_percent" not in data:
                data["sgst_percent"] = sgst
            if "igst_percent" not in data:
                data["igst_percent"] = igst
            titles = default_titles(scheme, gst_slab, rate)
            for key in ("title", "cgst_title", "sgst_title", "igst_title", "title_suffix"):
                if key not in data:
                    data[key] = titles[key]
            if "name" not in data:
                data["name"] = titles["name"]
        for key, value in data.items():
            setattr(row, key, value)
        dine = data.get("applies_dine_in", row.applies_dine_in)
        take = data.get("applies_takeaway", row.applies_takeaway)
        delivery = data.get("applies_delivery", row.applies_delivery)
        if not (dine or take or delivery):
            raise HTTPException(status_code=400, detail="Pick at least one order type")
        if scheme != "gst":
            row.scope = "items"
            ids = item_ids if item_ids is not None else row.menu_item_ids
            if not ids:
                raise HTTPException(status_code=400, detail="VAT / other tax applies to selected menu items — pick at least one dish")
            await self._replace_items(row, ids, scheme)
        else:
            row.scope = "venue"
            if item_ids is not None:
                await self._replace_items(row, [], "gst")
        if row.scheme == "gst" and row.is_active:
            await self._deactivate_other_gst(outlet_id, row.id)
        await self.db.commit()
        await self.db.refresh(row)
        return self._to_response(row)

    async def delete(self, owner: BusinessOwner, outlet_id: uuid.UUID, profile_id: uuid.UUID) -> None:
        row = await self._get(owner, outlet_id, profile_id)
        await self.db.delete(row)
        await self.db.commit()

    async def set_enabled(self, owner: BusinessOwner, outlet_id: uuid.UUID, enabled: bool) -> list[TaxProfileResponse]:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        rows = await self._all(outlet_id)
        for row in rows:
            row.is_active = enabled
        await self.db.commit()
        return [self._to_response(r) for r in rows]

    async def preview(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        payload: TaxPreviewRequest,
    ) -> TaxPreviewResponse:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        rows = await self._all(outlet_id)
        matching = [p for p in rows if applies_to_order(p, payload.order_type)]
        tax = compute_from_profiles(payload.amount_inr, matching, apply_tax=payload.apply_tax)
        pays = guest_pays(payload.amount_inr, tax)
        note = self._preview_note(tax, payload)
        return TaxPreviewResponse(
            amount_inr=money(payload.amount_inr),
            method=tax.method,
            tax_label=tax.label,
            tax_percent=tax.tax_percent,
            tax_amount=tax.tax_amount,
            cgst_amount=tax.cgst_amount,
            sgst_amount=tax.sgst_amount,
            igst_amount=tax.igst_amount,
            guest_pays=pays,
            lines=[TaxPreviewLine(title=t, amount_inr=a) for t, a in tax.lines],
            applied=tax.applied,
            note=note,
        )

    async def matching_profiles(
        self,
        outlet_id: uuid.UUID,
        order_type: OrderType,
    ) -> list[OutletTaxProfile]:
        rows = await self._all(outlet_id)
        return [p for p in rows if p.is_active and applies_to_order(p, order_type)]

    def _apply_create(self, row: OutletTaxProfile, payload: TaxProfileCreate) -> None:
        rate, cgst, sgst, igst = _fill_rates(payload.scheme, payload.gst_slab, payload.rate_percent)
        titles = default_titles(payload.scheme, payload.gst_slab, rate)
        row.name = (payload.name or "").strip() or titles["name"]
        row.scheme = payload.scheme
        row.gst_slab = payload.gst_slab if payload.scheme == "gst" else None
        row.rate_percent = rate
        row.cgst_percent = cgst
        row.sgst_percent = sgst
        row.igst_percent = igst
        row.title = (payload.title or "").strip() or titles["title"]
        row.cgst_title = payload.cgst_title or titles["cgst_title"]
        row.sgst_title = payload.sgst_title or titles["sgst_title"]
        row.igst_title = payload.igst_title or titles["igst_title"]
        row.title_suffix = payload.title_suffix or titles["title_suffix"]
        row.method = payload.method
        row.applies_dine_in = payload.applies_dine_in
        row.applies_takeaway = payload.applies_takeaway
        row.applies_delivery = payload.applies_delivery
        row.is_active = payload.is_active
        row.scope = "items" if payload.scheme != "gst" else "venue"
        row.notes = payload.notes

    async def _ensure_gst_catalog(self, outlet_id: uuid.UUID) -> None:
        existing = {p.gst_slab for p in await self._all(outlet_id) if p.scheme == "gst"}
        created = False
        for slab, rate, sort in GST_CATALOG:
            if slab in existing:
                continue
            titles = default_titles("gst", slab, rate)
            cgst, sgst, igst = fill_gst_split("gst", slab, rate)
            self.db.add(
                OutletTaxProfile(
                    outlet_id=outlet_id,
                    name=titles["name"],
                    scheme="gst",
                    gst_slab=slab,
                    rate_percent=rate,
                    cgst_percent=cgst,
                    sgst_percent=sgst,
                    igst_percent=igst,
                    title=titles["title"],
                    cgst_title=titles["cgst_title"],
                    sgst_title=titles["sgst_title"],
                    igst_title=titles["igst_title"],
                    title_suffix=titles["title_suffix"],
                    method="forward",
                    is_active=False,
                    scope="venue",
                    sort_order=sort,
                ),
            )
            created = True
        if created:
            await self.db.commit()

    async def _deactivate_other_gst(self, outlet_id: uuid.UUID, keep_id: uuid.UUID) -> None:
        for row in await self._all(outlet_id):
            if row.scheme == "gst" and row.id != keep_id and row.is_active:
                row.is_active = False

    async def _replace_items(self, row: OutletTaxProfile, item_ids: list, scheme: str) -> None:
        row.items.clear()
        if scheme == "gst" or not item_ids:
            return
        unique = list(dict.fromkeys(item_ids))
        result = await self.db.execute(
            select(MenuItem.id).where(MenuItem.id.in_(unique), MenuItem.outlet_id == row.outlet_id),
        )
        valid = {r[0] for r in result.all()}
        if len(valid) != len(unique):
            raise HTTPException(status_code=400, detail="One or more dishes are not on this venue menu")
        for item_id in unique:
            row.items.append(OutletTaxProfileItem(profile_id=row.id, menu_item_id=item_id))

    @staticmethod
    def _to_response(row: OutletTaxProfile) -> TaxProfileResponse:
        payload = TaxProfileResponse.model_validate(row)
        payload.menu_item_ids = list(row.menu_item_ids)
        payload.scope = row.scope or ("items" if row.scheme != "gst" else "venue")
        return payload

    async def _all(self, outlet_id: uuid.UUID) -> list[OutletTaxProfile]:
        result = await self.db.execute(
            select(OutletTaxProfile)
            .where(OutletTaxProfile.outlet_id == outlet_id)
            .order_by(OutletTaxProfile.sort_order, OutletTaxProfile.created_at),
        )
        return list(result.scalars().all())

    async def _next_sort(self, outlet_id: uuid.UUID) -> int:
        rows = await self._all(outlet_id)
        return (max((r.sort_order for r in rows), default=-1) + 1)

    async def _get(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        profile_id: uuid.UUID,
    ) -> OutletTaxProfile:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        result = await self.db.execute(
            select(OutletTaxProfile).where(
                OutletTaxProfile.id == profile_id,
                OutletTaxProfile.outlet_id == outlet_id,
            ),
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tax profile not found")
        return row

    @staticmethod
    def _preview_note(tax, payload: TaxPreviewRequest) -> str:
        if not payload.apply_tax:
            return "Tax is off for this bill. Guest pays the menu total."
        if not tax.applied:
            return "No active tax for this order type. Guest pays the menu total."
        if tax.method == "backward":
            return f"Inclusive {tax.label}: ₹{payload.amount_inr} already has tax. Shown tax is extracted, guest still pays ₹{payload.amount_inr}."
        if tax.method == "tax_on_tax":
            return f"Tax-on-tax {tax.label}: each next tax sits on the previous total."
        return f"Exclusive {tax.label}: tax is added on top of the menu price."
