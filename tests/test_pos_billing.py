from decimal import Decimal

from app.services.owner.order_pricing import (
    compute_bill_totals,
    default_tax_percent_for_business,
    money,
    resolve_tax_percent,
)


def test_gst_default_tax_when_registered():
    assert default_tax_percent_for_business(True, "22AAAAA0000A1Z5") == Decimal("5.00")
    assert default_tax_percent_for_business(False, None) == Decimal("0")
    assert resolve_tax_percent(True, "22AAAAA0000A1Z5", Decimal("0")) == Decimal("5.00")
    assert resolve_tax_percent(True, "22AAAAA0000A1Z5", Decimal("12")) == Decimal("12.00")


def test_compute_bill_with_discount_percent_and_tax():
    subtotal = Decimal("1000")
    discount, tax_amount, round_off, grand, taxable = compute_bill_totals(
        subtotal,
        Decimal("0"),
        Decimal("10"),
        Decimal("5"),
        True,
    )
    assert discount == Decimal("100.00")
    assert taxable == Decimal("900.00")
    assert tax_amount == Decimal("45.00")
    assert grand == Decimal("945.00")
    assert money(grand) == grand


def test_money_coerces_int():
    assert money(0) == Decimal("0.00")
    assert money(10) == Decimal("10.00")


def test_split_payment_totals():
    subtotal = Decimal("200")
    _, _, _, grand, _ = compute_bill_totals(subtotal, Decimal("0"), Decimal("0"), Decimal("0"), True)
    assert grand == Decimal("200.00")
    half = money(grand / 2)
    assert money(half + half) == grand
