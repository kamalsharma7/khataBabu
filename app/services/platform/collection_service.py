from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import OwnerRole, TenantStatus
from app.models.platform_admin import PlatformAdmin
from app.models.platform_collection import PlatformCollection
from app.models.tenant import Business
from app.schemas.platform.collection import (
    CollectionCallingList,
    CollectionCallingRow,
    CollectionCreate,
    CollectionHistoryResponse,
    CollectionResponse,
    CollectionVenueOption,
    RestaurantCollectionList,
    RestaurantCollectionRow,
)


def _money(value: Decimal | float | int) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


_PLATFORM_TZ = ZoneInfo("Asia/Kolkata")


def _calling_reference_date(as_of: date | None) -> date:
    return as_of if as_of is not None else datetime.now(_PLATFORM_TZ).date()


def _due_for_collection_calling(
    next_payment_date: date,
    today: date,
    window_days: int,
) -> bool:
    """Overdue, due today, or next payment within the next `window_days` calendar days."""
    window_end = today + timedelta(days=window_days)
    return next_payment_date <= window_end


class PlatformCollectionService:
    CALLING_WINDOW_DAYS = 3

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _load_onboarded_businesses(self) -> list[Business]:
        result = await self.db.execute(
            select(Business)
            .where(Business.status != TenantStatus.DRAFT)
            .options(selectinload(Business.outlets), selectinload(Business.owners))
            .order_by(Business.legal_name),
        )
        businesses = result.scalars().all()
        return [b for b in businesses if b.outlets]

    def _outlet(self, business: Business):
        return business.outlets[0]

    def _primary_owner(self, business: Business):
        owners = business.owners or []
        for owner in owners:
            if owner.role == OwnerRole.OWNER:
                return owner
        return owners[0] if owners else None

    async def list_venue_options(self) -> list[CollectionVenueOption]:
        options: list[CollectionVenueOption] = []
        for business in await self._load_onboarded_businesses():
            outlet = self._outlet(business)
            joining = business.created_at.date() if business.created_at else date.today()
            options.append(
                CollectionVenueOption(
                    business_id=business.id,
                    legal_name=business.legal_name,
                    outlet_name=outlet.name,
                    outlet_ref_code=outlet.ref_code,
                    city=business.city,
                    state=business.state,
                    status=business.status,
                    joining_date=joining,
                ),
            )
        return options

    async def _get_business(self, business_id: uuid.UUID) -> Business:
        result = await self.db.execute(
            select(Business)
            .where(Business.id == business_id)
            .options(selectinload(Business.outlets)),
        )
        business = result.scalar_one_or_none()
        if business is None or not business.outlets:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venue not found")
        if business.status == TenantStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Collections apply only after onboarding is complete",
            )
        return business

    async def create(self, payload: CollectionCreate, admin: PlatformAdmin) -> CollectionResponse:
        await self._get_business(payload.business_id)
        payment_date = payload.payment_date or date.today()
        if payload.next_payment_date < payment_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Next payment date must be on or after payment date",
            )
        row = PlatformCollection(
            business_id=payload.business_id,
            amount_inr=payload.amount_inr,
            payment_date=payment_date,
            next_payment_date=payload.next_payment_date,
            tenure_months=payload.tenure_months,
            notes=payload.notes.strip() if payload.notes else None,
            recorded_by_admin_id=admin.id,
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return CollectionResponse.model_validate(row)

    async def _collections_by_business(
        self,
    ) -> dict[uuid.UUID, list[PlatformCollection]]:
        result = await self.db.execute(
            select(PlatformCollection).order_by(
                PlatformCollection.next_payment_date.asc(),
                PlatformCollection.payment_date.desc(),
            ),
        )
        grouped: dict[uuid.UUID, list[PlatformCollection]] = defaultdict(list)
        for row in result.scalars().all():
            grouped[row.business_id].append(row)
        return dict(grouped)

    def _soonest_due_pack_for_calling(
        self,
        packs: list[PlatformCollection],
        today: date,
    ) -> PlatformCollection | None:
        due = [
            pack
            for pack in packs
            if _due_for_collection_calling(
                pack.next_payment_date,
                today,
                self.CALLING_WINDOW_DAYS,
            )
        ]
        if not due:
            return None
        return min(due, key=lambda pack: pack.next_payment_date)

    async def _latest_collections_by_business(
        self,
    ) -> dict[uuid.UUID, PlatformCollection]:
        result = await self.db.execute(
            select(PlatformCollection).order_by(
                PlatformCollection.payment_date.desc(),
                PlatformCollection.created_at.desc(),
            ),
        )
        latest: dict[uuid.UUID, PlatformCollection] = {}
        for row in result.scalars().all():
            if row.business_id not in latest:
                latest[row.business_id] = row
        return latest

    async def _totals_by_business(self) -> dict[uuid.UUID, tuple[Decimal, int]]:
        result = await self.db.execute(select(PlatformCollection))
        totals: dict[uuid.UUID, tuple[Decimal, int]] = defaultdict(
            lambda: (Decimal("0"), 0),
        )
        for row in result.scalars().all():
            amount, count = totals[row.business_id]
            totals[row.business_id] = (_money(amount + row.amount_inr), count + 1)
        return dict(totals)

    async def collection_calling(self, as_of: date | None = None) -> CollectionCallingList:
        today = _calling_reference_date(as_of)
        by_business = await self._collections_by_business()
        businesses = await self._load_onboarded_businesses()

        rows: list[CollectionCallingRow] = []
        for business in businesses:
            packs = by_business.get(business.id, [])
            if not packs:
                continue
            pack = self._soonest_due_pack_for_calling(packs, today)
            if pack is None:
                continue
            outlet = self._outlet(business)
            owner = self._primary_owner(business)
            days_until = (pack.next_payment_date - today).days
            rows.append(
                CollectionCallingRow(
                    business_id=business.id,
                    legal_name=business.legal_name,
                    outlet_name=outlet.name,
                    outlet_ref_code=outlet.ref_code,
                    city=business.city,
                    state=business.state,
                    status=business.status,
                    owner_name=owner.full_name if owner else None,
                    owner_mobile=owner.mobile if owner else None,
                    venue_phone=business.primary_phone,
                    amount_inr=pack.amount_inr,
                    tenure_months=pack.tenure_months,
                    payment_date=pack.payment_date,
                    next_payment_date=pack.next_payment_date,
                    days_until_due=days_until,
                    is_overdue=days_until < 0,
                    collection_id=pack.id,
                ),
            )

        rows.sort(key=lambda r: (r.next_payment_date, r.legal_name))
        return CollectionCallingList(
            as_of=today,
            due_within_days=self.CALLING_WINDOW_DAYS,
            rows=rows,
        )

    async def restaurant_collections(self) -> RestaurantCollectionList:
        latest = await self._latest_collections_by_business()
        totals = await self._totals_by_business()
        businesses = await self._load_onboarded_businesses()

        rows: list[RestaurantCollectionRow] = []
        for business in businesses:
            outlet = self._outlet(business)
            pack = latest.get(business.id)
            total_inr, pack_count = totals.get(business.id, (Decimal("0"), 0))
            joining = business.created_at.date() if business.created_at else date.today()
            rows.append(
                RestaurantCollectionRow(
                    business_id=business.id,
                    legal_name=business.legal_name,
                    outlet_name=outlet.name,
                    outlet_ref_code=outlet.ref_code,
                    city=business.city,
                    state=business.state,
                    status=business.status,
                    joining_date=joining,
                    plan_tier=business.plan_tier.value,
                    has_collection=pack is not None,
                    latest_amount_inr=pack.amount_inr if pack else None,
                    tenure_months=pack.tenure_months if pack else None,
                    latest_payment_date=pack.payment_date if pack else None,
                    next_payment_date=pack.next_payment_date if pack else None,
                    total_collected_inr=_money(total_inr),
                    pack_count=pack_count,
                ),
            )

        rows.sort(key=lambda r: (r.next_payment_date or date.max, r.legal_name))
        return RestaurantCollectionList(rows=rows)

    async def collection_history(self, business_id: uuid.UUID) -> CollectionHistoryResponse:
        business = await self._get_business(business_id)
        outlet = self._outlet(business)
        joining = business.created_at.date() if business.created_at else date.today()

        result = await self.db.execute(
            select(PlatformCollection)
            .where(PlatformCollection.business_id == business_id)
            .order_by(
                PlatformCollection.payment_date.desc(),
                PlatformCollection.created_at.desc(),
            ),
        )
        entries = result.scalars().all()
        total = _money(sum((e.amount_inr for e in entries), Decimal("0")))

        return CollectionHistoryResponse(
            business_id=business.id,
            legal_name=business.legal_name,
            outlet_name=outlet.name,
            outlet_ref_code=outlet.ref_code,
            city=business.city,
            state=business.state,
            joining_date=joining,
            total_collected_inr=total,
            entries=[CollectionResponse.model_validate(e) for e in entries],
        )
