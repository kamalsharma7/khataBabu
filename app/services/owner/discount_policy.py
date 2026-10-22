from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException, status

from app.models.compliance import BusinessPosSettings
from app.models.enums import OwnerRole
from app.models.tenant import BusinessOwner
from app.services.owner.business_settings_service import BusinessSettingsService
from app.services.owner.order_pricing import money


def effective_discount_percent(
    subtotal: Decimal,
    discount_amount: Decimal,
    discount_percent: Decimal,
) -> Decimal:
    if subtotal <= 0:
        return Decimal("0")
    if discount_percent > 0:
        return discount_percent
    if discount_amount <= 0:
        return Decimal("0")
    return money(discount_amount / subtotal * Decimal("100"))


async def assert_discount_allowed(
    db_settings: BusinessSettingsService,
    owner: BusinessOwner,
    pos: BusinessPosSettings,
    subtotal: Decimal,
    discount_amount: Decimal,
    discount_percent: Decimal,
    manager_approval_pin: str | None,
) -> None:
    eff = effective_discount_percent(subtotal, discount_amount, discount_percent)
    if eff <= 0:
        return
    if eff > pos.max_discount_percent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Discount cannot exceed {pos.max_discount_percent}%",
        )
    worker_cap = pos.worker_max_discount_percent
    if owner.role == OwnerRole.OWNER or owner.role == OwnerRole.ADMIN:
        return
    if eff <= worker_cap:
        return
    ok = await db_settings.verify_manager_pin(owner.business_id, manager_approval_pin)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Discount above {worker_cap}% needs manager approval PIN",
        )
