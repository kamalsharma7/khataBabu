from types import SimpleNamespace

from app.models.enums import FoodType
from app.services.owner.menu_food_type import effective_food_type, pick_default_variation


def test_effective_inherits_item_when_modifiers_null():
    item = SimpleNamespace(food_type=FoodType.VEG)
    var = SimpleNamespace(food_type=None)
    assert effective_food_type(item, var, []) == FoodType.VEG


def test_addon_non_veg_upgrades_line():
    item = SimpleNamespace(food_type=FoodType.VEG)
    addon = SimpleNamespace(food_type=FoodType.NON_VEG)
    assert effective_food_type(item, None, [addon]) == FoodType.NON_VEG


def test_variation_non_veg_overrides_veg_item():
    item = SimpleNamespace(food_type=FoodType.VEG)
    var = SimpleNamespace(food_type=FoodType.NON_VEG)
    assert effective_food_type(item, var, []) == FoodType.NON_VEG


def test_variation_egg_upgrades_veg_item():
    item = SimpleNamespace(food_type=FoodType.VEG)
    var = SimpleNamespace(food_type=FoodType.EGG)
    assert effective_food_type(item, var, []) == FoodType.EGG


def test_non_veg_beats_egg_on_same_line():
    item = SimpleNamespace(food_type=FoodType.VEG)
    var = SimpleNamespace(food_type=FoodType.EGG)
    nv_top = SimpleNamespace(food_type=FoodType.NON_VEG)
    assert effective_food_type(item, var, [nv_top]) == FoodType.NON_VEG


def test_veg_variation_and_no_toppings_stays_veg():
    item = SimpleNamespace(food_type=FoodType.VEG)
    var = SimpleNamespace(food_type=None)
    assert effective_food_type(item, var, []) == FoodType.VEG


def test_pick_default_prefers_variation_matching_item_diet():
    item = SimpleNamespace(food_type=FoodType.VEG)
    egg_var = SimpleNamespace(food_type=FoodType.EGG, is_default=False)
    veg_var = SimpleNamespace(food_type=None, is_default=False)
    picked = pick_default_variation(item, [egg_var, veg_var])
    assert picked is veg_var


def test_egg_topping_upgrades_veg_line():
    item = SimpleNamespace(food_type=FoodType.VEG)
    var = SimpleNamespace(food_type=None)
    addon = SimpleNamespace(food_type=FoodType.EGG)
    assert effective_food_type(item, var, [addon]) == FoodType.EGG
