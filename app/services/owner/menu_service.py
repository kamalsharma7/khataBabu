from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import FoodType
from app.models.menu import MenuAddonGroup, MenuCategory, MenuItem, MenuItemAddon, MenuItemVariation
from app.models.order import PosOrderLine
from app.models.tenant import BusinessOwner
from app.schemas.owner.menu import (
    MenuAddonGroupInput,
    MenuAddonGroupResponse,
    MenuAddonInput,
    MenuAddonResponse,
    MenuCategoryCreate,
    MenuCategoryUpdate,
    MenuItemCreate,
    MenuItemModifiersUpdate,
    MenuItemResponse,
    MenuItemUpdate,
    MenuVariationInput,
    MenuVariationResponse,
)
from app.services.owner.access import assert_business_operational, get_outlet_for_owner


def _food_type_from_payload(food_type: FoodType | None, is_veg: bool) -> FoodType:
    if food_type is not None:
        return food_type
    return FoodType.VEG if is_veg else FoodType.NON_VEG


def _variation_leaves(variations: list[MenuVariationInput]) -> list[MenuVariationInput]:
    leaves: list[MenuVariationInput] = []
    for v in variations:
        if v.children:
            leaves.extend(v.children)
        else:
            leaves.append(v)
    return leaves


def _normalize_variations(variations: list[MenuVariationInput]) -> list[MenuVariationInput]:
    if not variations:
        return []
    leaves = _variation_leaves(variations)
    default_count = sum(1 for v in leaves if v.is_default)
    if default_count > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only one sellable variation (the size you tap on POS) can be default",
        )
    if default_count == 0 and leaves:
        leaves[0].is_default = True
    return variations


def _base_price_from_variations(variations: list[MenuVariationInput], fallback: Decimal) -> Decimal:
    if not variations:
        return fallback
    normalized = _normalize_variations(variations)
    for leaf in _variation_leaves(normalized):
        if leaf.is_default:
            return leaf.price
    leaves = _variation_leaves(normalized)
    return leaves[0].price if leaves else fallback


def _make_variation(payload: MenuVariationInput, idx: int, is_default: bool) -> MenuItemVariation:
    return MenuItemVariation(
        name=payload.name.strip(),
        price=payload.price,
        sort_order=payload.sort_order if payload.sort_order else idx,
        is_default=is_default,
        is_available=payload.is_available,
        weight_grams=payload.weight_grams,
        food_type=payload.food_type,
    )


def _attach_modifiers(
    item: MenuItem,
    variations: list[MenuVariationInput],
    addons: list[MenuAddonInput],
    addon_groups: list[MenuAddonGroupInput] | None = None,
) -> None:
    normalized = _normalize_variations(variations)
    for idx, v in enumerate(normalized):
        parent = _make_variation(v, idx, is_default=v.is_default and not v.children)
        item.variations.append(parent)
        for cidx, child in enumerate(v.children):
            kid = _make_variation(child, cidx, is_default=child.is_default)
            kid.parent = parent
            item.variations.append(kid)

    groups = list(addon_groups or [])
    if not groups and addons:
        groups = [MenuAddonGroupInput(name="Toppings", addons=addons)]
    for gidx, group in enumerate(groups):
        row = MenuAddonGroup(
            name=group.name.strip() or "Toppings",
            min_select=group.min_select,
            max_select=group.max_select,
            sort_order=group.sort_order if group.sort_order else gidx,
        )
        item.addon_groups.append(row)
        for aidx, addon in enumerate(group.addons):
            if not addon.name.strip():
                continue
            item.addons.append(
                MenuItemAddon(
                    name=addon.name.strip(),
                    price=addon.price,
                    sort_order=addon.sort_order if addon.sort_order else aidx,
                    is_available=addon.is_available,
                    weight_grams=addon.weight_grams,
                    food_type=addon.food_type,
                    group=row,
                ),
            )


def _variation_response(row: MenuItemVariation, children: list[MenuItemVariation]) -> MenuVariationResponse:
    return MenuVariationResponse(
        id=row.id,
        name=row.name,
        price=row.price,
        sort_order=row.sort_order,
        is_default=row.is_default,
        is_available=row.is_available,
        weight_grams=row.weight_grams,
        food_type=row.food_type,
        parent_id=row.parent_id,
        children=[_variation_response(c, []) for c in children],
    )


def item_to_response(item: MenuItem) -> MenuItemResponse:
    all_vars = list(item.variations)
    kids_by_parent: dict = {}
    roots: list[MenuItemVariation] = []
    for v in sorted(all_vars, key=lambda r: (r.sort_order, r.name)):
        if v.parent_id:
            kids_by_parent.setdefault(v.parent_id, []).append(v)
        else:
            roots.append(v)
    variations = [_variation_response(v, kids_by_parent.get(v.id, [])) for v in roots]
    addons = [MenuAddonResponse.model_validate(a) for a in item.addons]
    groups: list[MenuAddonGroupResponse] = []
    for g in item.addon_groups:
        groups.append(
            MenuAddonGroupResponse(
                id=g.id,
                name=g.name,
                min_select=g.min_select,
                max_select=g.max_select,
                sort_order=g.sort_order,
                addons=[MenuAddonResponse.model_validate(a) for a in g.addons] or [a for a in addons if a.group_id == g.id],
            ),
        )
    if not groups and addons:
        groups = [
            MenuAddonGroupResponse(
                id=item.id,
                name="Toppings",
                min_select=0,
                max_select=None,
                sort_order=0,
                addons=addons,
            ),
        ]
    return MenuItemResponse(
        id=item.id,
        outlet_id=item.outlet_id,
        category_id=item.category_id,
        name=item.name,
        description=item.description,
        price=item.price,
        short_code=item.short_code,
        is_veg=item.is_veg,
        food_type=item.food_type,
        is_available=item.is_available,
        sort_order=item.sort_order,
        gst_applicable=item.gst_applicable,
        cgst_percent=item.cgst_percent,
        sgst_percent=item.sgst_percent,
        variations=variations,
        addons=addons,
        addon_groups=groups,
    )


class OwnerMenuService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_categories(self, owner: BusinessOwner, outlet_id: uuid.UUID) -> list[MenuCategory]:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        result = await self.db.execute(
            select(MenuCategory)
            .where(MenuCategory.outlet_id == outlet_id)
            .order_by(MenuCategory.sort_order, MenuCategory.name),
        )
        return list(result.scalars().all())

    async def create_category(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        payload: MenuCategoryCreate,
    ) -> MenuCategory:
        assert_business_operational(owner.business)
        await get_outlet_for_owner(self.db, owner, outlet_id)
        category = MenuCategory(
            outlet_id=outlet_id,
            name=payload.name.strip(),
            sort_order=payload.sort_order,
        )
        self.db.add(category)
        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Category already exists")
        await self.db.refresh(category)
        return category

    async def update_category(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        category_id: uuid.UUID,
        payload: MenuCategoryUpdate,
    ) -> MenuCategory:
        assert_business_operational(owner.business)
        category = await self._get_category(owner, outlet_id, category_id)
        if payload.name is not None:
            category.name = payload.name.strip()
        if payload.sort_order is not None:
            category.sort_order = payload.sort_order
        await self.db.commit()
        await self.db.refresh(category)
        return category

    async def delete_category(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        category_id: uuid.UUID,
    ) -> None:
        assert_business_operational(owner.business)
        category = await self._get_category(owner, outlet_id, category_id)
        item_ids = await self.db.scalars(
            select(MenuItem.id).where(
                MenuItem.category_id == category_id,
                MenuItem.outlet_id == outlet_id,
            ),
        )
        for menu_item_id in item_ids:
            await self._detach_menu_item_from_order_lines(menu_item_id)
        await self.db.delete(category)
        await self.db.commit()

    async def list_items(self, owner: BusinessOwner, outlet_id: uuid.UUID) -> list[MenuItem]:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        result = await self.db.execute(
            select(MenuItem)
            .where(MenuItem.outlet_id == outlet_id)
            .options(
                selectinload(MenuItem.variations),
                selectinload(MenuItem.addons),
                selectinload(MenuItem.addon_groups).selectinload(MenuAddonGroup.addons),
            )
            .order_by(MenuItem.sort_order, MenuItem.name),
        )
        return list(result.scalars().unique().all())

    async def create_item(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        payload: MenuItemCreate,
    ) -> MenuItem:
        assert_business_operational(owner.business)
        await self._get_category(owner, outlet_id, payload.category_id)
        base_price = _base_price_from_variations(payload.variations, payload.price)
        food_type = _food_type_from_payload(payload.food_type, payload.is_veg)
        item = MenuItem(
            outlet_id=outlet_id,
            category_id=payload.category_id,
            name=payload.name.strip(),
            description=payload.description,
            price=base_price,
            short_code=payload.short_code,
            is_veg=food_type != FoodType.NON_VEG,
            food_type=food_type,
            is_available=payload.is_available,
            sort_order=payload.sort_order,
            gst_applicable=payload.gst_applicable,
            cgst_percent=payload.cgst_percent if payload.gst_applicable else Decimal("0"),
            sgst_percent=payload.sgst_percent if payload.gst_applicable else Decimal("0"),
        )
        _attach_modifiers(item, payload.variations, payload.addons, payload.addon_groups)
        self.db.add(item)
        await self.db.commit()
        return await self._get_item_loaded(owner, outlet_id, item.id)

    async def update_item(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        item_id: uuid.UUID,
        payload: MenuItemUpdate,
    ) -> MenuItem:
        assert_business_operational(owner.business)
        item = await self._get_item_loaded(owner, outlet_id, item_id)
        if payload.category_id is not None:
            await self._get_category(owner, outlet_id, payload.category_id)
            item.category_id = payload.category_id
        if payload.name is not None:
            item.name = payload.name.strip()
        if payload.description is not None:
            item.description = payload.description
        if payload.price is not None:
            # Open orders keep line unit_price; settled bills use stored line_total / bill totals.
            item.price = payload.price
        if payload.short_code is not None:
            item.short_code = payload.short_code
        if payload.food_type is not None:
            item.food_type = payload.food_type
            item.is_veg = payload.food_type != FoodType.NON_VEG
        elif payload.is_veg is not None:
            item.is_veg = payload.is_veg
            item.food_type = FoodType.VEG if payload.is_veg else FoodType.NON_VEG
        if payload.is_available is not None:
            item.is_available = payload.is_available
        if payload.sort_order is not None:
            item.sort_order = payload.sort_order
        if payload.gst_applicable is not None:
            item.gst_applicable = payload.gst_applicable
        if payload.cgst_percent is not None:
            item.cgst_percent = payload.cgst_percent
        if payload.sgst_percent is not None:
            item.sgst_percent = payload.sgst_percent
        if item.gst_applicable:
            if item.cgst_percent <= 0 and item.sgst_percent <= 0:
                item.cgst_percent = Decimal("2.5")
                item.sgst_percent = Decimal("2.5")
        else:
            item.cgst_percent = Decimal("0")
            item.sgst_percent = Decimal("0")
        await self.db.commit()
        return await self._get_item_loaded(owner, outlet_id, item_id)

    async def replace_item_modifiers(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        item_id: uuid.UUID,
        payload: MenuItemModifiersUpdate,
    ) -> MenuItem:
        assert_business_operational(owner.business)
        item = await self._get_item_loaded(owner, outlet_id, item_id)
        await self.db.execute(delete(MenuItemAddon).where(MenuItemAddon.menu_item_id == item.id))
        await self.db.execute(delete(MenuAddonGroup).where(MenuAddonGroup.menu_item_id == item.id))
        await self.db.execute(
            delete(MenuItemVariation).where(
                MenuItemVariation.menu_item_id == item.id,
                MenuItemVariation.parent_id.is_not(None),
            ),
        )
        await self.db.execute(delete(MenuItemVariation).where(MenuItemVariation.menu_item_id == item.id))
        await self.db.flush()
        await self.db.refresh(item, attribute_names=["variations", "addons", "addon_groups"])
        _attach_modifiers(item, payload.variations, payload.addons, payload.addon_groups)
        if payload.variations:
            item.price = _base_price_from_variations(payload.variations, item.price)
        await self.db.commit()
        return await self._get_item_loaded(owner, outlet_id, item_id)

    async def delete_item(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> None:
        assert_business_operational(owner.business)
        item = await self._get_item(owner, outlet_id, item_id)
        await self._detach_menu_item_from_order_lines(item.id)
        await self.db.delete(item)
        await self.db.commit()

    async def _detach_menu_item_from_order_lines(self, menu_item_id: uuid.UUID) -> None:
        """Keep billed/KOT history; order lines store item_name snapshots."""
        await self.db.execute(
            update(PosOrderLine)
            .where(PosOrderLine.menu_item_id == menu_item_id)
            .values(menu_item_id=None),
        )

    async def _get_category(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        category_id: uuid.UUID,
    ) -> MenuCategory:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        result = await self.db.execute(
            select(MenuCategory).where(
                MenuCategory.id == category_id,
                MenuCategory.outlet_id == outlet_id,
            ),
        )
        category = result.scalar_one_or_none()
        if category is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
        return category

    async def _get_item(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> MenuItem:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        result = await self.db.execute(
            select(MenuItem).where(
                MenuItem.id == item_id,
                MenuItem.outlet_id == outlet_id,
            ),
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")
        return item

    async def _get_item_loaded(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> MenuItem:
        await get_outlet_for_owner(self.db, owner, outlet_id)
        result = await self.db.execute(
            select(MenuItem)
            .where(MenuItem.id == item_id, MenuItem.outlet_id == outlet_id)
            .options(
                selectinload(MenuItem.variations),
                selectinload(MenuItem.addons),
                selectinload(MenuItem.addon_groups).selectinload(MenuAddonGroup.addons),
            ),
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")
        return item
