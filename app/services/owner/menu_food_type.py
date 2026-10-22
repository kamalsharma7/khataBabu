from __future__ import annotations

from typing import Protocol

from app.models.enums import FoodType

_STRICTNESS = {
    FoodType.VEG: 0,
    FoodType.EGG: 1,
    FoodType.NON_VEG: 2,
}


class _HasFoodType(Protocol):
    food_type: FoodType | None


def _modifier_effective(base: FoodType, modifier_ft: FoodType | None) -> FoodType:
    return modifier_ft if modifier_ft is not None else base


def pick_default_variation(
    item: _HasFoodType,
    variations: list[_HasFoodType],
) -> _HasFoodType | None:
    """POS auto-select: explicit default, else variation matching item diet, else first."""
    if not variations:
        return None
    for v in variations:
        if getattr(v, "is_default", False):
            return v
    base = item.food_type
    for v in variations:
        if _modifier_effective(base, v.food_type) == base:
            return v
    return variations[0]


def effective_food_type(
    item: _HasFoodType,
    variation: _HasFoodType | None,
    addons: list[_HasFoodType],
) -> FoodType:
    """
    Billing line diet from selected variation + selected toppings only.
    Priority: non-veg > egg > veg.
    """
    base = item.food_type
    diets: list[FoodType] = []
    if variation is not None:
        diets.append(_modifier_effective(base, variation.food_type))
    else:
        diets.append(base)
    for addon in addons:
        diets.append(_modifier_effective(base, addon.food_type))
    if FoodType.NON_VEG in diets:
        return FoodType.NON_VEG
    if FoodType.EGG in diets:
        return FoodType.EGG
    return FoodType.VEG
