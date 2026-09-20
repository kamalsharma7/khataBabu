from __future__ import annotations

from decimal import Decimal

from app.models.enums import OrderLineStatus
from app.models.order import PosOrder, PosOrderLine

MONEY = Decimal("0.01")


def money(value: Decimal | int | float | str | None) -> Decimal:
    if value is None:
        value = Decimal("0")
    elif not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(MONEY)


def compute_time_charge(minutes: int, hourly_rate: Decimal) -> Decimal:
    if minutes <= 0 or hourly_rate <= 0:
        return Decimal("0")
    return money(Decimal(minutes) * hourly_rate / Decimal("60"))


def order_subtotal(order: PosOrder) -> Decimal:
    return order_effective_subtotal(order)


def order_effective_subtotal(order: PosOrder, lines: list[PosOrderLine] | None = None) -> Decimal:
    source = lines if lines is not None else order.lines
    base = subtotal_from_lines(source)
    charge = order.time_charge if order.time_charge is not None else Decimal("0")
    return money(base + charge)


def subtotal_from_lines(lines: list[PosOrderLine]) -> Decimal:
    total = Decimal("0")
    for line in lines:
        if line.status != OrderLineStatus.CANCELLED:
            total += line.line_total
    return money(total)


def compute_bill_totals(
    subtotal: Decimal,
    discount_amount: Decimal,
    discount_percent: Decimal,
    tax_percent: Decimal,
    round_to_rupee: bool = True,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
    subtotal = money(subtotal)
    discount = money(discount_amount)
    if discount_percent > 0:
        discount = money(subtotal * discount_percent / Decimal("100"))
    if discount > subtotal:
        discount = subtotal
    taxable = money(subtotal - discount)
    tax_amount = money(taxable * tax_percent / Decimal("100"))
    grand = money(taxable + tax_amount)
    round_off = Decimal("0")
    if round_to_rupee:
        rounded = money(Decimal(grand.to_integral_value()))
        round_off = money(rounded - grand)
        grand = rounded
    return discount, tax_amount, round_off, grand, taxable


def line_total(unit_price: Decimal, addons_total: Decimal, quantity: int) -> Decimal:
    return money((unit_price + addons_total) * quantity)


# India restaurant GST (food service) default when business is GST-registered.
DEFAULT_GST_TAX_PERCENT = Decimal("5")


def default_tax_percent_for_business(gst_registered: bool, gstin: str | None) -> Decimal:
    if gst_registered and gstin and gstin.strip():
        return DEFAULT_GST_TAX_PERCENT
    return Decimal("0")


def resolve_tax_percent(
    gst_registered: bool,
    gstin: str | None,
    requested: Decimal,
) -> Decimal:
    if requested > 0:
        return money(requested)
    return default_tax_percent_for_business(gst_registered, gstin)
