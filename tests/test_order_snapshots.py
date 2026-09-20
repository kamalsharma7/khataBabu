"""Historical bill data must not follow live menu or table renames."""

from app.models.order import PosOrder
from app.models.venue import VenueTable
from app.services.owner.order_service import historical_table_label


def test_historical_table_label_prefers_snapshot() -> None:
    order = PosOrder(
        outlet_id=None,  # type: ignore[arg-type]
        order_type=None,  # type: ignore[arg-type]
        order_number=1,
        table_label_snapshot="Table 5 (old name)",
        venue_table_id=None,
    )
    table = VenueTable(
        outlet_id=None,  # type: ignore[arg-type]
        area_id=None,  # type: ignore[arg-type]
        label="Table 5 (renamed)",
        sort_order=0,
    )
    assert historical_table_label(order, table) == "Table 5 (old name)"


def test_historical_table_label_falls_back_to_table() -> None:
    order = PosOrder(
        outlet_id=None,  # type: ignore[arg-type]
        order_type=None,  # type: ignore[arg-type]
        order_number=1,
        table_label_snapshot=None,
        venue_table_id=None,
    )
    table = VenueTable(
        outlet_id=None,  # type: ignore[arg-type]
        area_id=None,  # type: ignore[arg-type]
        label="AC 3",
        sort_order=0,
    )
    assert historical_table_label(order, table) == "AC 3"
