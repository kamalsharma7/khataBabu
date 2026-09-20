from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.owner import get_current_owner
from app.db.deps import get_db
from app.models.tenant import BusinessOwner
from app.schemas.owner.venue import (
    AreaCreate,
    AreaResponse,
    AreaUpdate,
    TableBulkCreate,
    TableCreate,
    TableResponse,
    TableUpdate,
)
from app.services.owner.venue_service import OwnerVenueService

router = APIRouter(prefix="/outlets/{outlet_id}")


@router.get("/areas", response_model=list[AreaResponse])
async def list_areas(
    outlet_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> list[AreaResponse]:
    service = OwnerVenueService(db)
    areas = await service.list_areas(owner, outlet_id)
    return [AreaResponse.model_validate(a) for a in areas]


@router.post("/areas", response_model=AreaResponse, status_code=status.HTTP_201_CREATED)
async def create_area(
    outlet_id: uuid.UUID,
    body: AreaCreate,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> AreaResponse:
    service = OwnerVenueService(db)
    area = await service.create_area(owner, outlet_id, body)
    return AreaResponse.model_validate(area)


@router.patch("/areas/{area_id}", response_model=AreaResponse)
async def update_area(
    outlet_id: uuid.UUID,
    area_id: uuid.UUID,
    body: AreaUpdate,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> AreaResponse:
    service = OwnerVenueService(db)
    area = await service.update_area(owner, outlet_id, area_id, body)
    return AreaResponse.model_validate(area)


@router.delete("/areas/{area_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_area(
    outlet_id: uuid.UUID,
    area_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = OwnerVenueService(db)
    await service.delete_area(owner, outlet_id, area_id)


@router.get("/areas/{area_id}/tables", response_model=list[TableResponse])
async def list_tables(
    outlet_id: uuid.UUID,
    area_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> list[TableResponse]:
    service = OwnerVenueService(db)
    tables = await service.list_tables(owner, outlet_id, area_id)
    return [TableResponse.model_validate(t) for t in tables]


@router.post(
    "/areas/{area_id}/tables/bulk",
    response_model=list[TableResponse],
    status_code=status.HTTP_201_CREATED,
)
async def bulk_create_tables(
    outlet_id: uuid.UUID,
    area_id: uuid.UUID,
    body: TableBulkCreate,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> list[TableResponse]:
    service = OwnerVenueService(db)
    tables = await service.bulk_create_tables(owner, outlet_id, area_id, body)
    return [TableResponse.model_validate(t) for t in tables]


@router.post("/areas/{area_id}/tables", response_model=TableResponse, status_code=status.HTTP_201_CREATED)
async def create_table(
    outlet_id: uuid.UUID,
    area_id: uuid.UUID,
    body: TableCreate,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> TableResponse:
    service = OwnerVenueService(db)
    table = await service.create_table(owner, outlet_id, area_id, body)
    return TableResponse.model_validate(table)


@router.patch("/tables/{table_id}", response_model=TableResponse)
async def update_table(
    outlet_id: uuid.UUID,
    table_id: uuid.UUID,
    body: TableUpdate,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> TableResponse:
    service = OwnerVenueService(db)
    table = await service.update_table(owner, outlet_id, table_id, body)
    return TableResponse.model_validate(table)


@router.delete("/tables/{table_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_table(
    outlet_id: uuid.UUID,
    table_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = OwnerVenueService(db)
    await service.delete_table(owner, outlet_id, table_id)
