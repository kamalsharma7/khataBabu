"""Owner RBAC permission codes."""

from __future__ import annotations

from app.models.enums import OwnerRole

PERM_POS_BILLING = "pos.billing"
PERM_POS_MENU = "pos.menu"
PERM_POS_FLOOR = "pos.floor"
PERM_POS_INVENTORY = "pos.inventory"
PERM_POS_BILLS = "pos.bills"
PERM_POS_REFUND = "pos.refund"
PERM_ANALYTICS = "analytics.overview"
PERM_SETTINGS_VIEW = "settings.view"
PERM_SETTINGS_ALL = "settings.all"
PERM_AUDIT_VIEW = "audit.view"
PERM_OPS_DAY_CLOSE = "ops.day_close"
PERM_OPS_DAY_REOPEN = "ops.day_close.reopen"


def permissions_for_role(role: OwnerRole) -> list[str]:
    if role in (OwnerRole.WORKER, OwnerRole.EMPLOYEE):
        return [PERM_POS_BILLING, PERM_POS_BILLS]
    if role == OwnerRole.ADMIN:
        return [
            PERM_POS_BILLING,
            PERM_POS_MENU,
            PERM_POS_FLOOR,
            PERM_POS_INVENTORY,
            PERM_POS_BILLS,
            PERM_POS_REFUND,
            PERM_ANALYTICS,
            PERM_SETTINGS_VIEW,
            PERM_OPS_DAY_CLOSE,
            PERM_AUDIT_VIEW,
        ]
    return [
        PERM_POS_BILLING,
        PERM_POS_MENU,
        PERM_POS_FLOOR,
        PERM_POS_INVENTORY,
        PERM_POS_BILLS,
        PERM_POS_REFUND,
        PERM_ANALYTICS,
        PERM_SETTINGS_VIEW,
        PERM_SETTINGS_ALL,
        PERM_OPS_DAY_CLOSE,
        PERM_OPS_DAY_REOPEN,
        PERM_AUDIT_VIEW,
    ]


def has_permission(role: OwnerRole, permission: str) -> bool:
    return permission in permissions_for_role(role)
