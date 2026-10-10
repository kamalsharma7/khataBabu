import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.owner import get_current_owner
from app.db.deps import get_db
from app.models.tenant import BusinessOwner
from app.schemas.owner.inventory import (
    InventoryAnalyticsResponse,
    InventoryItemCreate,
    InventoryItemResponse,
    InventoryItemUpdate,
    MenuInventoryLinkInput,
)
from app.services.owner.inventory_service import OwnerInventoryService

router = APIRouter(prefix="/outlets/{outlet_id}/inventory", tags=["owner-inventory"])


@router.get("", response_model=list[InventoryItemResponse])
async def list_inventory(
    outlet_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> list[InventoryItemResponse]:
    service = OwnerInventoryService(db)
    items = await service.list_items(owner, outlet_id)
    return [InventoryItemResponse.model_validate(i) for i in items]


@router.post("", response_model=InventoryItemResponse, status_code=status.HTTP_201_CREATED)
async def create_inventory_item(
    outlet_id: uuid.UUID,
    body: InventoryItemCreate,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> InventoryItemResponse:
    service = OwnerInventoryService(db)
    item = await service.create_item(owner, outlet_id, body)
    return InventoryItemResponse.model_validate(item)


@router.patch("/{item_id}", response_model=InventoryItemResponse)
async def update_inventory_item(
    outlet_id: uuid.UUID,
    item_id: uuid.UUID,
    body: InventoryItemUpdate,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> InventoryItemResponse:
    service = OwnerInventoryService(db)
    item = await service.update_item(owner, outlet_id, item_id, body)
    return InventoryItemResponse.model_validate(item)


@router.post("/menu-items/{menu_item_id}/link", status_code=status.HTTP_204_NO_CONTENT)
async def link_menu_inventory(
    outlet_id: uuid.UUID,
    menu_item_id: uuid.UUID,
    body: MenuInventoryLinkInput,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = OwnerInventoryService(db)
    await service.link_menu_item(owner, outlet_id, menu_item_id, body)


@router.get("/analytics", response_model=InventoryAnalyticsResponse)
async def inventory_analytics(
    outlet_id: uuid.UUID,
    days: int = Query(default=90, ge=7, le=365),
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> InventoryAnalyticsResponse:
    service = OwnerInventoryService(db)
    return await service.analytics(owner, outlet_id, days)
