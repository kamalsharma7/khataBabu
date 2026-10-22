"""Shared helpers for outlet sales aggregation (no service imports)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.schemas.owner.inventory import ItemQtyRow
from app.services.owner.order_pricing import money

OUTLET_TZ = ZoneInfo("Asia/Kolkata")


def sale_agg_key(menu_item_id: uuid.UUID | None, item_name: str) -> str:
    if menu_item_id is not None:
        return str(menu_item_id)
    return f"name:{item_name.strip()}"


def bucket_add(
    bucket: dict[str, ItemQtyRow],
    menu_item_id: uuid.UUID | None,
    item_name: str,
    amount: Decimal,
) -> None:
    key = sale_agg_key(menu_item_id, item_name)
    if key in bucket:
        bucket[key].quantity = money(bucket[key].quantity + amount)
    else:
        bucket[key] = ItemQtyRow(
            menu_item_id=menu_item_id,
            item_name=item_name,
            quantity=amount,
        )
