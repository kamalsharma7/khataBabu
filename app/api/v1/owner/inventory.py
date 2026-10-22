import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.owner import get_current_owner
from app.api.deps.permissions import require_permission
from app.services.owner.permissions import PERM_POS_INVENTORY
from app.db.deps import get_db
from app.models.tenant import BusinessOwner
from app.schemas.owner.inventory import (
    BulkDailyStockBody,
    InventoryItemCreate,
    InventoryItemResponse,
    InventoryItemUpdate,
    InventorySalesAnalyticsResponse,
    InventoryTransactionResponse,
    MenuInventoryLinkInput,
    ReplaceRecipeBomBody,
    SetDailyStockBody,
    StockAdjustBody,
    TrackMenuStockBody,
)
from app.services.owner.inventory_service import OwnerInventoryService

router = APIRouter(
    prefix="/outlets/{outlet_id}/inventory",
    tags=["owner-inventory"],
    dependencies=[Depends(require_permission(PERM_POS_INVENTORY))],
)


@router.get("", response_model=list[InventoryItemResponse])
async def list_inventory(
    outlet_id: uuid.UUID,
    kind: str = Query(default="all", pattern="^(all|raw|daily)$"),
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> list[InventoryItemResponse]:
    service = OwnerInventoryService(db)
    return await service.list_items(owner, outlet_id, kind)


@router.get("/sales-analytics", response_model=InventorySalesAnalyticsResponse)
async def inventory_sales_analytics(
    outlet_id: uuid.UUID,
    days: int = Query(default=30, ge=7, le=365),
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> InventorySalesAnalyticsResponse:
    service = OwnerInventoryService(db)
    return await service.sales_analytics(owner, outlet_id, days)


@router.post("/track-menu", response_model=InventoryItemResponse)
async def track_menu_stock(
    outlet_id: uuid.UUID,
    body: TrackMenuStockBody,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> InventoryItemResponse:
    service = OwnerInventoryService(db)
    return await service.track_menu_stock(owner, outlet_id, body)


@router.post("", response_model=InventoryItemResponse, status_code=status.HTTP_201_CREATED)
async def create_inventory_item(
    outlet_id: uuid.UUID,
    body: InventoryItemCreate,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> InventoryItemResponse:
    service = OwnerInventoryService(db)
    return await service.create_item(owner, outlet_id, body)


@router.post("/daily-stock/bulk", response_model=list[InventoryItemResponse])
async def bulk_set_daily_stock(
    outlet_id: uuid.UUID,
    body: BulkDailyStockBody,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> list[InventoryItemResponse]:
    service = OwnerInventoryService(db)
    return await service.bulk_set_daily_stock(owner, outlet_id, body)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_inventory_item(
    outlet_id: uuid.UUID,
    item_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = OwnerInventoryService(db)
    await service.delete_item(owner, outlet_id, item_id)


@router.patch("/{item_id}", response_model=InventoryItemResponse)
async def update_inventory_item(
    outlet_id: uuid.UUID,
    item_id: uuid.UUID,
    body: InventoryItemUpdate,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> InventoryItemResponse:
    service = OwnerInventoryService(db)
    return await service.update_item(owner, outlet_id, item_id, body)


@router.post("/{item_id}/daily-stock", response_model=InventoryItemResponse)
async def set_daily_stock(
    outlet_id: uuid.UUID,
    item_id: uuid.UUID,
    body: SetDailyStockBody,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> InventoryItemResponse:
    service = OwnerInventoryService(db)
    return await service.set_daily_stock(owner, outlet_id, item_id, body)


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


@router.put(
    "/menu-items/{menu_item_id}/recipe-bom",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def replace_recipe_bom(
    outlet_id: uuid.UUID,
    menu_item_id: uuid.UUID,
    body: ReplaceRecipeBomBody,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = OwnerInventoryService(db)
    await service.replace_raw_bom(owner, outlet_id, menu_item_id, body)


@router.post("/{item_id}/adjust", response_model=InventoryItemResponse)
async def adjust_inventory_stock(
    outlet_id: uuid.UUID,
    item_id: uuid.UUID,
    body: StockAdjustBody,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> InventoryItemResponse:
    service = OwnerInventoryService(db)
    return await service.adjust_stock(owner, outlet_id, item_id, body)


@router.get("/{item_id}/transactions", response_model=list[InventoryTransactionResponse])
async def list_inventory_transactions(
    outlet_id: uuid.UUID,
    item_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> list[InventoryTransactionResponse]:
    service = OwnerInventoryService(db)
    return await service.list_transactions(owner, outlet_id, item_id)


@router.delete(
    "/menu-items/{menu_item_id}/link/{inventory_item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_menu_inventory(
    outlet_id: uuid.UUID,
    menu_item_id: uuid.UUID,
    inventory_item_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = OwnerInventoryService(db)
    await service.unlink_menu_item(owner, outlet_id, menu_item_id, inventory_item_id)
