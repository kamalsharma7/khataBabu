from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.owner import get_current_owner
from app.db.deps import get_db
from app.models.tenant import BusinessOwner
from app.schemas.owner.menu import (
    MenuCategoryCreate,
    MenuCategoryResponse,
    MenuCategoryUpdate,
    MenuItemCreate,
    MenuItemModifiersUpdate,
    MenuItemResponse,
    MenuItemUpdate,
)
from app.services.owner.menu_service import OwnerMenuService

router = APIRouter(prefix="/outlets/{outlet_id}/menu")


@router.get("/categories", response_model=list[MenuCategoryResponse])
async def list_categories(
    outlet_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> list[MenuCategoryResponse]:
    service = OwnerMenuService(db)
    rows = await service.list_categories(owner, outlet_id)
    return [MenuCategoryResponse.model_validate(r) for r in rows]


@router.post("/categories", response_model=MenuCategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    outlet_id: uuid.UUID,
    body: MenuCategoryCreate,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> MenuCategoryResponse:
    service = OwnerMenuService(db)
    row = await service.create_category(owner, outlet_id, body)
    return MenuCategoryResponse.model_validate(row)


@router.patch("/categories/{category_id}", response_model=MenuCategoryResponse)
async def update_category(
    outlet_id: uuid.UUID,
    category_id: uuid.UUID,
    body: MenuCategoryUpdate,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> MenuCategoryResponse:
    service = OwnerMenuService(db)
    row = await service.update_category(owner, outlet_id, category_id, body)
    return MenuCategoryResponse.model_validate(row)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    outlet_id: uuid.UUID,
    category_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = OwnerMenuService(db)
    await service.delete_category(owner, outlet_id, category_id)


@router.get("/items", response_model=list[MenuItemResponse])
async def list_items(
    outlet_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> list[MenuItemResponse]:
    service = OwnerMenuService(db)
    rows = await service.list_items(owner, outlet_id)
    return [MenuItemResponse.model_validate(r) for r in rows]


@router.post("/items", response_model=MenuItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    outlet_id: uuid.UUID,
    body: MenuItemCreate,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> MenuItemResponse:
    service = OwnerMenuService(db)
    row = await service.create_item(owner, outlet_id, body)
    return MenuItemResponse.model_validate(row)


@router.patch("/items/{item_id}", response_model=MenuItemResponse)
async def update_item(
    outlet_id: uuid.UUID,
    item_id: uuid.UUID,
    body: MenuItemUpdate,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> MenuItemResponse:
    service = OwnerMenuService(db)
    row = await service.update_item(owner, outlet_id, item_id, body)
    return MenuItemResponse.model_validate(row)


@router.put("/items/{item_id}/modifiers", response_model=MenuItemResponse)
async def replace_item_modifiers(
    outlet_id: uuid.UUID,
    item_id: uuid.UUID,
    body: MenuItemModifiersUpdate,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> MenuItemResponse:
    service = OwnerMenuService(db)
    row = await service.replace_item_modifiers(owner, outlet_id, item_id, body)
    return MenuItemResponse.model_validate(row)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    outlet_id: uuid.UUID,
    item_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = OwnerMenuService(db)
    await service.delete_item(owner, outlet_id, item_id)
