"""How a rupee of food becomes tax + what the guest pays.

GSTIN is not consulted. Only active outlet tax profiles apply.

Methods (PetPooja-compatible):
- forward: menu price is exclusive; tax is added (₹100 + 5% = ₹105)
- backward: menu price already includes tax; we extract it (₹100 incl. 5% → tax ₹4.76)
- tax_on_tax: each next tax sits on (base + previous tax)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable, Optional

from app.models.enums import OrderType
from app.models.tax import OutletTaxProfile
from app.services.owner.order_pricing import money

HUNDRED = Decimal("100")

GST_SLABS: dict[str, Decimal] = {
    "gst_5": Decimal("5"),
    "gst_18": Decimal("18"),
    "gst_40": Decimal("40"),
    "igst": Decimal("5"),
}


@dataclass
class TaxComputation:
    tax_percent: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    cgst_amount: Decimal = Decimal("0")
    sgst_amount: Decimal = Decimal("0")
    igst_amount: Decimal = Decimal("0")
    method: str = "forward"
    label: Optional[str] = None
    lines: list[tuple[str, Decimal]] = field(default_factory=list)
    applied: bool = False
    added_amount: Decimal = Decimal("0")


def applies_to_order(profile: OutletTaxProfile, order_type: OrderType) -> bool:
    if order_type == OrderType.DINE_IN:
        return profile.applies_dine_in
    if order_type == OrderType.TAKEAWAY:
        return profile.applies_takeaway
    if order_type == OrderType.DELIVERY:
        return profile.applies_delivery
    return True


def fill_gst_split(scheme: str, gst_slab: Optional[str], rate: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """Return (cgst, sgst, igst) for a total rate."""
    rate = money(rate)
    if scheme == "gst" and gst_slab == "igst":
        return Decimal("0"), Decimal("0"), rate
    if scheme == "gst":
        half = money(rate / 2)
        return half, money(rate - half), Decimal("0")
    return Decimal("0"), Decimal("0"), Decimal("0")


def _rate_label(rate: Decimal) -> str:
    n = money(rate)
    if n == n.to_integral():
        return str(int(n))
    return format(n, "f").rstrip("0").rstrip(".")


def default_titles(scheme: str, gst_slab: Optional[str], rate: Decimal) -> dict:
    rate_s = _rate_label(rate)
    if scheme == "gst" and gst_slab == "igst":
        return {
            "title": f"IGST {rate_s}%",
            "cgst_title": None,
            "sgst_title": None,
            "igst_title": f"IGST@{rate_s}%",
            "title_suffix": f"@{rate_s}%",
            "name": f"IGST {rate_s}%",
        }
    if scheme == "gst":
        half = _rate_label(rate / 2)
        return {
            "title": f"GST {rate_s}%",
            "cgst_title": f"CGST@{half}%",
            "sgst_title": f"SGST@{half}%",
            "igst_title": None,
            "title_suffix": f"@{half}%",
            "name": f"GST {rate_s}%",
        }
    if scheme == "vat":
        return {
            "title": f"VAT {rate_s}%",
            "cgst_title": None,
            "sgst_title": None,
            "igst_title": None,
            "title_suffix": f"@{rate_s}%",
            "name": f"VAT {rate_s}%",
        }
    return {
        "title": f"Tax {rate_s}%",
        "cgst_title": None,
        "sgst_title": None,
        "igst_title": None,
        "title_suffix": f"@{rate_s}%",
        "name": f"Other tax {rate_s}%",
    }


def compute_from_profiles(
    taxable: Decimal,
    profiles: Iterable[OutletTaxProfile],
    *,
    apply_tax: bool = True,
) -> TaxComputation:
    rows = [p for p in profiles if p.is_active and money(p.rate_percent) > 0]
    if not apply_tax or not rows:
        return TaxComputation()

    method = rows[0].method or "forward"
    combined_rate = money(sum((money(p.rate_percent) for p in rows), Decimal("0")))
    label = " + ".join(p.title for p in rows)

    if method == "backward":
        inclusive = money(taxable)
        tax_amount = money(inclusive * combined_rate / (HUNDRED + combined_rate)) if combined_rate else Decimal("0")
        return _split_amounts(rows, tax_amount, combined_rate, method, label)

    running = money(taxable)
    tax_amount = Decimal("0")
    cgst = Decimal("0")
    sgst = Decimal("0")
    igst = Decimal("0")
    lines: list[tuple[str, Decimal]] = []
    for profile in rows:
        rate = money(profile.rate_percent)
        base = running if method == "tax_on_tax" else money(taxable)
        chunk = money(base * rate / HUNDRED)
        tax_amount += chunk
        c, s, i, titled = _allocate_chunk(profile, chunk)
        cgst += c
        sgst += s
        igst += i
        lines.extend(titled)
        if method == "tax_on_tax":
            running = money(running + chunk)

    added = Decimal("0") if method == "backward" else money(tax_amount)
    return TaxComputation(
        tax_percent=combined_rate,
        tax_amount=money(tax_amount),
        cgst_amount=money(cgst),
        sgst_amount=money(sgst),
        igst_amount=money(igst),
        method=method,
        label=label,
        lines=lines,
        applied=tax_amount > 0,
        added_amount=added,
    )


def merge_tax(left: TaxComputation, right: TaxComputation) -> TaxComputation:
    if not right.applied:
        return left
    if not left.applied:
        return right
    labels = [part for part in (left.label, right.label) if part]
    return TaxComputation(
        tax_percent=money(left.tax_percent + right.tax_percent),
        tax_amount=money(left.tax_amount + right.tax_amount),
        cgst_amount=money(left.cgst_amount + right.cgst_amount),
        sgst_amount=money(left.sgst_amount + right.sgst_amount),
        igst_amount=money(left.igst_amount + right.igst_amount),
        method=left.method if left.applied else right.method,
        label=" + ".join(labels) if labels else None,
        lines=left.lines + right.lines,
        applied=True,
        added_amount=money(left.added_amount + right.added_amount),
    )


def compute_for_bill(
    taxable: Decimal,
    line_taxables: Iterable[tuple[Optional[object], Decimal]],
    profiles: Iterable[OutletTaxProfile],
    *,
    apply_tax: bool = True,
) -> TaxComputation:
    """GST hits the whole bill. VAT / other hits only the dishes linked to that rule."""
    rows = [p for p in profiles if p.is_active and money(p.rate_percent) > 0]
    if not apply_tax or not rows:
        return TaxComputation()
    gst = [p for p in rows if p.scheme == "gst"]
    item_rules = [p for p in rows if p.scheme != "gst"]
    result = compute_from_profiles(taxable, gst, apply_tax=True)
    for profile in item_rules:
        ids = {str(i) for i in profile.menu_item_ids}
        if not ids:
            continue
        base = money(sum((amt for mid, amt in line_taxables if mid is not None and str(mid) in ids), Decimal("0")))
        result = merge_tax(result, compute_from_profiles(base, [profile], apply_tax=True))
    return result


def guest_pays(taxable: Decimal, tax: TaxComputation, tip: Decimal = Decimal("0")) -> Decimal:
    """What the customer hands over (before rupee round-off)."""
    return money(taxable + tax.added_amount + tip)


def _split_amounts(
    profiles: list[OutletTaxProfile],
    tax_amount: Decimal,
    combined_rate: Decimal,
    method: str,
    label: str,
) -> TaxComputation:
    cgst = Decimal("0")
    sgst = Decimal("0")
    igst = Decimal("0")
    lines: list[tuple[str, Decimal]] = []
    remaining = tax_amount
    for idx, profile in enumerate(profiles):
        if combined_rate <= 0:
            share = Decimal("0")
        elif idx == len(profiles) - 1:
            share = remaining
        else:
            share = money(tax_amount * money(profile.rate_percent) / combined_rate)
            remaining = money(remaining - share)
        c, s, i, titled = _allocate_chunk(profile, share)
        cgst += c
        sgst += s
        igst += i
        lines.extend(titled)
    added = Decimal("0") if method == "backward" else money(tax_amount)
    return TaxComputation(
        tax_percent=combined_rate,
        tax_amount=money(tax_amount),
        cgst_amount=money(cgst),
        sgst_amount=money(sgst),
        igst_amount=money(igst),
        method=method,
        label=label,
        lines=lines,
        applied=tax_amount > 0,
        added_amount=added,
    )


def _allocate_chunk(profile: OutletTaxProfile, chunk: Decimal) -> tuple[Decimal, Decimal, Decimal, list[tuple[str, Decimal]]]:
    rate = money(profile.rate_percent)
    if rate <= 0 or chunk <= 0:
        return Decimal("0"), Decimal("0"), Decimal("0"), []
    cgst_p = money(profile.cgst_percent)
    sgst_p = money(profile.sgst_percent)
    igst_p = money(profile.igst_percent)
    if igst_p > 0 and cgst_p == 0 and sgst_p == 0:
        title = profile.igst_title or profile.title
        return Decimal("0"), Decimal("0"), money(chunk), [(title, money(chunk))]
    parts = cgst_p + sgst_p + igst_p
    if parts <= 0:
        title = profile.title
        return Decimal("0"), Decimal("0"), Decimal("0"), [(title, money(chunk))]
    cgst = money(chunk * cgst_p / parts)
    sgst = money(chunk * sgst_p / parts)
    igst = money(chunk - cgst - sgst) if igst_p > 0 else Decimal("0")
    if igst_p <= 0:
        sgst = money(chunk - cgst)
    lines: list[tuple[str, Decimal]] = []
    if cgst:
        lines.append((profile.cgst_title or "CGST", cgst))
    if sgst:
        lines.append((profile.sgst_title or "SGST", sgst))
    if igst:
        lines.append((profile.igst_title or "IGST", igst))
    return cgst, sgst, igst, lines
