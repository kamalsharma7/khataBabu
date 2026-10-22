from decimal import Decimal
from uuid import uuid4

from app.schemas.owner.inventory import ItemQtyRow
from app.services.owner.sales_analytics_helpers import bucket_add, sale_agg_key


def test_sale_agg_key_separates_menu_items():
    a, b = uuid4(), uuid4()
    assert sale_agg_key(a, "Roti") != sale_agg_key(b, "Roti")
    assert sale_agg_key(None, "Roti") == "name:Roti"
    assert sale_agg_key(None, "Coke") == "name:Coke"


def test_bucket_add_accumulates_per_item():
    bucket: dict[str, ItemQtyRow] = {}
    mid = uuid4()
    bucket_add(bucket, mid, "Roti", Decimal("2"))
    bucket_add(bucket, mid, "Roti", Decimal("3"))
    other = uuid4()
    bucket_add(bucket, other, "Coke", Decimal("1"))
    assert len(bucket) == 2
    assert bucket[sale_agg_key(mid, "Roti")].quantity == Decimal("5.00")
    assert bucket[sale_agg_key(other, "Coke")].quantity == Decimal("1.00")
