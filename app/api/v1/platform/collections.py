from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.platform import get_current_platform_admin
from app.db.deps import get_db
from app.models.platform_admin import PlatformAdmin
from app.schemas.platform.collection import (
    CollectionCallingList,
    CollectionCreate,
    CollectionHistoryResponse,
    CollectionResponse,
    CollectionVenueOption,
    RestaurantCollectionList,
)
from app.services.platform.collection_service import PlatformCollectionService

router = APIRouter()


@router.get("/venues", response_model=list[CollectionVenueOption])
async def list_collection_venues(
    db: AsyncSession = Depends(get_db),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> list[CollectionVenueOption]:
    service = PlatformCollectionService(db)
    return await service.list_venue_options()


@router.post("", response_model=CollectionResponse, status_code=201)
async def create_collection(
    body: CollectionCreate,
    db: AsyncSession = Depends(get_db),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> CollectionResponse:
    service = PlatformCollectionService(db)
    return await service.create(body, admin)


@router.get("/calling", response_model=CollectionCallingList)
async def collection_calling(
    db: AsyncSession = Depends(get_db),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> CollectionCallingList:
    service = PlatformCollectionService(db)
    return await service.collection_calling()


@router.get("/restaurants", response_model=RestaurantCollectionList)
async def restaurant_collections(
    db: AsyncSession = Depends(get_db),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> RestaurantCollectionList:
    service = PlatformCollectionService(db)
    return await service.restaurant_collections()


@router.get("/businesses/{business_id}/history", response_model=CollectionHistoryResponse)
async def venue_collection_history(
    business_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> CollectionHistoryResponse:
    service = PlatformCollectionService(db)
    return await service.collection_history(business_id)
