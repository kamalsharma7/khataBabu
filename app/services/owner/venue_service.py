from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import BusinessOwner
from app.models.venue import ResourceKind, VenueArea, VenueTable
from app.schemas.owner.venue import AreaCreate, AreaUpdate, TableBulkCreate, TableCreate, TableUpdate
from app.services.owner.access import assert_business_operational, get_outlet_for_owner


def _table_labels(prefix: str, count: int, start_number: int) -> list[str]:
    label_prefix = prefix.strip() or "Table"
    return [f"{label_prefix} {start_number + i}" for i in range(count)]


class OwnerVenueService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_areas(self, owner: BusinessOwner, outlet_id: uuid.UUID) -> list[VenueArea]:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        result = await self.db.execute(
            select(VenueArea)
            .where(VenueArea.outlet_id == outlet_id)
            .order_by(VenueArea.sort_order, VenueArea.name),
        )
        return list(result.scalars().all())

    async def create_area(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        payload: AreaCreate,
    ) -> VenueArea:
        assert_business_operational(owner.business)
        await get_outlet_for_owner(self.db, owner, outlet_id)
        area = VenueArea(
            outlet_id=outlet_id,
            name=payload.name.strip(),
            sort_order=payload.sort_order,
        )
        self.db.add(area)
        try:
            await self.db.flush()
            if payload.initial_table_count and payload.initial_table_count > 0:
                self._add_tables(
                    outlet_id=outlet_id,
                    area_id=area.id,
                    labels=_table_labels(
                        payload.table_label_prefix,
                        payload.initial_table_count,
                        start_number=1,
                    ),
                )
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Area name or table label already exists",
            )
        await self.db.refresh(area)
        return area

    async def update_area(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        area_id: uuid.UUID,
        payload: AreaUpdate,
    ) -> VenueArea:
        assert_business_operational(owner.business)
        area = await self._get_area(owner, outlet_id, area_id)
        if payload.name is not None:
            area.name = payload.name.strip()
        if payload.sort_order is not None:
            area.sort_order = payload.sort_order
        await self.db.commit()
        await self.db.refresh(area)
        return area

    async def delete_area(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        area_id: uuid.UUID,
    ) -> None:
        assert_business_operational(owner.business)
        area = await self._get_area(owner, outlet_id, area_id)
        await self.db.delete(area)
        await self.db.commit()

    async def list_tables(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        area_id: uuid.UUID,
    ) -> list[VenueTable]:
        await self._get_area(owner, outlet_id, area_id)
        result = await self.db.execute(
            select(VenueTable)
            .where(VenueTable.area_id == area_id)
            .order_by(VenueTable.sort_order, VenueTable.label),
        )
        return list(result.scalars().all())

    async def create_table(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        area_id: uuid.UUID,
        payload: TableCreate,
    ) -> VenueTable:
        assert_business_operational(owner.business)
        await self._get_area(owner, outlet_id, area_id)
        if payload.resource_kind == ResourceKind.TIME_BASED and payload.hourly_rate is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="hourly_rate is required for time-based resources",
            )
        table = VenueTable(
            outlet_id=outlet_id,
            area_id=area_id,
            label=payload.label.strip(),
            capacity=payload.capacity,
            resource_kind=payload.resource_kind,
            hourly_rate=payload.hourly_rate,
            sort_order=payload.sort_order,
        )
        self.db.add(table)
        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Table label already exists in this area",
            )
        await self.db.refresh(table)
        return table

    async def bulk_create_tables(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        area_id: uuid.UUID,
        payload: TableBulkCreate,
    ) -> list[VenueTable]:
        assert_business_operational(owner.business)
        await self._get_area(owner, outlet_id, area_id)
        labels = _table_labels(payload.table_label_prefix, payload.count, payload.start_number)
        tables = self._add_tables(outlet_id=outlet_id, area_id=area_id, labels=labels)
        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="One or more table labels already exist in this area",
            )
        for table in tables:
            await self.db.refresh(table)
        return tables

    def _add_tables(
        self,
        outlet_id: uuid.UUID,
        area_id: uuid.UUID,
        labels: list[str],
    ) -> list[VenueTable]:
        created: list[VenueTable] = []
        for sort_order, label in enumerate(labels):
            table = VenueTable(
                outlet_id=outlet_id,
                area_id=area_id,
                label=label,
                resource_kind=ResourceKind.DINE_TABLE,
                sort_order=sort_order,
            )
            self.db.add(table)
            created.append(table)
        return created

    async def update_table(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        table_id: uuid.UUID,
        payload: TableUpdate,
    ) -> VenueTable:
        assert_business_operational(owner.business)
        table = await self._get_table(owner, outlet_id, table_id)
        if payload.area_id is not None:
            await self._get_area(owner, outlet_id, payload.area_id)
            table.area_id = payload.area_id
        if payload.label is not None:
            table.label = payload.label.strip()
        if payload.capacity is not None:
            table.capacity = payload.capacity
        if payload.resource_kind is not None:
            table.resource_kind = payload.resource_kind
        if payload.hourly_rate is not None:
            table.hourly_rate = payload.hourly_rate
        if payload.sort_order is not None:
            table.sort_order = payload.sort_order
        kind = table.resource_kind
        if kind == ResourceKind.TIME_BASED and table.hourly_rate is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="hourly_rate is required for time-based resources",
            )
        await self.db.commit()
        await self.db.refresh(table)
        return table

    async def delete_table(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        table_id: uuid.UUID,
    ) -> None:
        assert_business_operational(owner.business)
        table = await self._get_table(owner, outlet_id, table_id)
        await self.db.delete(table)
        await self.db.commit()

    async def _get_area(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        area_id: uuid.UUID,
    ) -> VenueArea:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        result = await self.db.execute(
            select(VenueArea).where(
                VenueArea.id == area_id,
                VenueArea.outlet_id == outlet_id,
            ),
        )
        area = result.scalar_one_or_none()
        if area is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Area not found")
        return area

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
