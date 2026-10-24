from decimal import Decimal

from app.schemas.owner.menu import MenuVariationInput
from app.services.owner.menu_service import _base_price_from_variations, _normalize_variations, _variation_leaves


def _type(name: str, children: list[MenuVariationInput], **kwargs) -> MenuVariationInput:
    return MenuVariationInput(name=name, children=children, **kwargs)


def _size(name: str, price: str, is_default: bool = False) -> MenuVariationInput:
    return MenuVariationInput(name=name, price=Decimal(price), is_default=is_default)


def test_leaves_are_sizes_under_types():
    tree = [
        _type("Paneer", [_size("Half", "80"), _size("Full", "140", is_default=True)]),
        _type("Veg", [_size("Half", "70"), _size("Full", "120")]),
    ]
    leaves = _variation_leaves(tree)
    assert [f"{v.name}:{v.price}" for v in leaves] == [
        "Half:80",
        "Full:140",
        "Half:70",
        "Full:120",
    ]


def test_flat_variation_is_its_own_leaf():
    tree = [MenuVariationInput(name="Large", price=Decimal("199"))]
    leaves = _variation_leaves(tree)
    assert len(leaves) == 1
    assert leaves[0].name == "Large"


def test_normalize_defaults_first_leaf():
    tree = [
        _type("Paneer", [_size("Half", "80"), _size("Full", "140")]),
    ]
    normalized = _normalize_variations(tree)
    leaves = _variation_leaves(normalized)
    assert leaves[0].is_default is True
    assert leaves[1].is_default is False


def test_base_price_uses_default_leaf():
    tree = [
        _type("Paneer", [_size("Half", "80"), _size("Full", "140", is_default=True)]),
        _type("Veg", [_size("Half", "70"), _size("Full", "120")]),
    ]
    assert _base_price_from_variations(tree, Decimal("0")) == Decimal("140")
