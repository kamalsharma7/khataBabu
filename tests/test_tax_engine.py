from decimal import Decimal

from app.models.tax import OutletTaxProfile
from app.services.owner.order_pricing import default_tax_percent_for_business, resolve_tax_percent
from app.services.owner.tax_engine import compute_from_profiles, fill_gst_split, guest_pays


def _gst5() -> OutletTaxProfile:
    return OutletTaxProfile(
        name="GST 5%",
        scheme="gst",
        gst_slab="gst_5",
        rate_percent=Decimal("5"),
        cgst_percent=Decimal("2.5"),
        sgst_percent=Decimal("2.5"),
        igst_percent=Decimal("0"),
        title="GST 5%",
        cgst_title="CGST@2.5%",
        sgst_title="SGST@2.5%",
        method="forward",
        is_active=True,
    )


def test_gstin_never_turns_tax_on():
    assert default_tax_percent_for_business(True, "22AAAAA0000A1Z5") == Decimal("0")
    assert default_tax_percent_for_business(False, None) == Decimal("0")
    assert resolve_tax_percent(True, "22AAAAA0000A1Z5", Decimal("12")) == Decimal("0")


def test_gst_split():
    assert fill_gst_split("gst", "gst_5", Decimal("5")) == (Decimal("2.50"), Decimal("2.50"), Decimal("0.00"))
    assert fill_gst_split("gst", "igst", Decimal("5")) == (Decimal("0.00"), Decimal("0.00"), Decimal("5.00"))


def test_forward_gst_on_100():
    tax = compute_from_profiles(Decimal("100"), [_gst5()], apply_tax=True)
    assert tax.applied
    assert tax.tax_amount == Decimal("5.00")
    assert tax.cgst_amount == Decimal("2.50")
    assert tax.sgst_amount == Decimal("2.50")
    assert guest_pays(Decimal("100"), tax) == Decimal("105.00")


def test_backward_extracts_tax():
    row = _gst5()
    row.method = "backward"
    tax = compute_from_profiles(Decimal("100"), [row], apply_tax=True)
    assert tax.tax_amount == Decimal("4.76")
    assert guest_pays(Decimal("100"), tax) == Decimal("100.00")


def test_vat_only_on_selected_items():
    vat = OutletTaxProfile(
        name="VAT 10%",
        scheme="vat",
        rate_percent=Decimal("10"),
        title="VAT 10%",
        method="forward",
        is_active=True,
    )
    vat.items = []

    class _Item:
        def __init__(self, mid):
            self.menu_item_id = mid

    from app.models.tax import OutletTaxProfileItem
    from uuid import uuid4
    from app.services.owner.tax_engine import compute_for_bill

    a = uuid4()
    b = uuid4()
    vat.items = [OutletTaxProfileItem(menu_item_id=a)]
    tax = compute_for_bill(
        Decimal("200"),
        [(a, Decimal("80")), (b, Decimal("120"))],
        [_gst5(), vat],
        apply_tax=True,
    )
    # GST 5% on 200 = 10, VAT 10% on item A 80 = 8
    assert tax.tax_amount == Decimal("18.00")
    assert guest_pays(Decimal("200"), tax) == Decimal("218.00")


def test_tax_off_or_empty():
    tax = compute_from_profiles(Decimal("100"), [_gst5()], apply_tax=False)
    assert tax.tax_amount == Decimal("0")
    assert guest_pays(Decimal("100"), tax) == Decimal("100.00")
    assert compute_from_profiles(Decimal("100"), []).tax_amount == Decimal("0")
