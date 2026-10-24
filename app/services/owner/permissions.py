"""Venue-wise RBAC.

Owner / admin always have a full role catalog (they run the venue).
Receptionist / worker start with a safe counter default; the owner can tick
or untick each operation **per outlet** — same login, different rights if the
business has more than one branch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import OwnerRole

PERM_DENIED_MESSAGE = "You don't have permission for this operation."

PERM_POS_BILLING = "pos.billing"
PERM_POS_MENU = "pos.menu"
PERM_POS_FLOOR = "pos.floor"
PERM_POS_INVENTORY = "pos.inventory"
PERM_POS_BILLS = "pos.bills"
PERM_POS_REFUND = "pos.refund"
PERM_POS_DISCOUNT = "pos.discount"
PERM_POS_CANCEL = "pos.cancel"
PERM_POS_PAY_LATER = "pos.pay_later"
PERM_RECIPES = "recipes.manage"
PERM_TAX_VIEW = "tax.view"
PERM_TAX_EDIT = "tax.edit"
PERM_PURCHASES = "purchases.manage"
PERM_CRM_VIEW = "crm.view"
PERM_CRM_EDIT = "crm.edit"
PERM_CRM_DELETE = "crm.delete"
PERM_ANALYTICS = "analytics.overview"
PERM_SETTINGS_VIEW = "settings.view"
PERM_SETTINGS_ALL = "settings.all"
PERM_AUDIT_VIEW = "audit.view"
PERM_OPS_DAY_CLOSE = "ops.day_close"
PERM_OPS_DAY_REOPEN = "ops.day_close.reopen"
PERM_STAFF_MANAGE = "staff.permissions"

MANAGER_ROLES = {OwnerRole.OWNER, OwnerRole.ADMIN}
STAFF_ROLES = {OwnerRole.EMPLOYEE, OwnerRole.WORKER}


@dataclass(frozen=True)
class PermDef:
    code: str
    label: str
    hint: str
    group: str
    group_label: str
    staff_assignable: bool
    default_staff: bool
    dangerous: bool = False


PERMISSION_CATALOG: tuple[PermDef, ...] = (
    PermDef(PERM_POS_BILLING, "Take orders & settle", "Open tables, add items, KOT, collect payment.", "billing", "Billing counter", True, True),
    PermDef(PERM_POS_BILLS, "View / reprint bills", "Today's and past invoices from this outlet.", "billing", "Billing counter", True, True),
    PermDef(PERM_POS_DISCOUNT, "Give discount", "Still capped by your worker % — bigger needs manager PIN.", "billing", "Billing counter", True, True),
    PermDef(PERM_POS_CANCEL, "Cancel order / void item", "Cancel a running bill or void a kitchen item.", "billing", "Billing counter", True, False, True),
    PermDef(PERM_POS_PAY_LATER, "Pay later / khata", "Leave the bill open as due.", "billing", "Billing counter", True, True),
    PermDef(PERM_POS_REFUND, "Refund a settled bill", "Money-back on a closed invoice.", "billing", "Billing counter", True, False, True),
    PermDef(PERM_POS_FLOOR, "Change table layout", "Add / rename / delete areas and tables.", "front", "Floor & menu", True, False),
    PermDef(PERM_POS_MENU, "Add / edit menu", "Categories, items, prices, variations.", "front", "Floor & menu", True, False),
    PermDef(PERM_RECIPES, "Item recipes", "What goes into a dish (BOM).", "front", "Floor & menu", True, False),
    PermDef(PERM_TAX_VIEW, "See tax setup", "GST / VAT rules this venue applies on bills.", "front", "Floor & menu", True, False),
    PermDef(PERM_TAX_EDIT, "Add / edit tax", "Turn GST on or off, change slab, method, order types.", "front", "Floor & menu", True, False),
    PermDef(PERM_POS_INVENTORY, "Daily stock & raw materials", "Aaj ka stock, wastage, raw material ledger.", "store", "Store", True, False),
    PermDef(PERM_PURCHASES, "Purchases & vendor pay", "Vendor bills, outstanding, stock-in.", "store", "Store", True, False),
    PermDef(PERM_CRM_VIEW, "See customers", "Customer list, lookup at billing, insights.", "crm", "Customers", True, True),
    PermDef(PERM_CRM_EDIT, "Add / edit customers", "Save name, mobile, birthday from billing or CRM.", "crm", "Customers", True, True),
    PermDef(PERM_CRM_DELETE, "Delete customers", "Remove a guest from the CRM (bills stay).", "crm", "Customers", True, False, True),
    PermDef(PERM_ANALYTICS, "Sales & CRM overview", "Overview PIN screen and CRM analytics.", "reports", "Reports & day end", True, False),
    PermDef(PERM_AUDIT_VIEW, "Audit log", "Who changed what on this venue.", "reports", "Reports & day end", True, False),
    PermDef(PERM_OPS_DAY_CLOSE, "Day close", "Close the business day and cash drawer.", "reports", "Reports & day end", True, False),
    PermDef(PERM_SETTINGS_VIEW, "View settings", "Read GST / invoice / discount policy.", "locked", "Owner only", False, False),
    PermDef(PERM_SETTINGS_ALL, "Change settings & PIN", "Edit policy, manager PIN, business profile.", "locked", "Owner only", False, False),
    PermDef(PERM_OPS_DAY_REOPEN, "Reopen a closed day", "Only the owner should unlock yesterday.", "locked", "Owner only", False, False),
    PermDef(PERM_STAFF_MANAGE, "Staff permissions", "Who can do what at this venue.", "locked", "Owner only", False, False),
)

_CATALOG_BY_CODE = {p.code: p for p in PERMISSION_CATALOG}
STAFF_ASSIGNABLE = tuple(p.code for p in PERMISSION_CATALOG if p.staff_assignable)
STAFF_DEFAULTS = tuple(p.code for p in PERMISSION_CATALOG if p.default_staff)
ALL_PERM_CODES = tuple(p.code for p in PERMISSION_CATALOG)


def is_manager(role: OwnerRole) -> bool:
    return role in MANAGER_ROLES


def is_staff(role: OwnerRole) -> bool:
    return role in STAFF_ROLES


def catalog_groups() -> list[dict]:
    groups: list[dict] = []
    seen: dict[str, dict] = {}
    for item in PERMISSION_CATALOG:
        bucket = seen.get(item.group)
        if bucket is None:
            bucket = {
                "id": item.group,
                "label": item.group_label,
                "staff_assignable": item.staff_assignable,
                "permissions": [],
            }
            seen[item.group] = bucket
            groups.append(bucket)
        bucket["permissions"].append(
            {
                "code": item.code,
                "label": item.label,
                "hint": item.hint,
                "staff_assignable": item.staff_assignable,
                "default_staff": item.default_staff,
                "dangerous": item.dangerous,
            },
        )
    return groups


def permissions_for_role(role: OwnerRole) -> list[str]:
    """Role ceiling — used for owner/admin, and as fallback before grants exist."""
    if is_staff(role):
        return list(STAFF_DEFAULTS)
    if role == OwnerRole.ADMIN:
        return [p.code for p in PERMISSION_CATALOG if p.code != PERM_OPS_DAY_REOPEN]
    return list(ALL_PERM_CODES)


def has_permission(role: OwnerRole, permission: str) -> bool:
    return permission in permissions_for_role(role)


async def resolve_permissions(
    db: AsyncSession,
    owner,
    outlet_id: Optional[UUID] = None,
) -> list[str]:
    """Effective permissions for this login at this venue."""
    if is_manager(owner.role):
        return permissions_for_role(owner.role)

    from app.models.staff_permission import StaffPermissionGrant

    stmt = select(StaffPermissionGrant).where(StaffPermissionGrant.owner_id == owner.id)
    if outlet_id is not None:
        stmt = stmt.where(StaffPermissionGrant.outlet_id == outlet_id)
    rows = list((await db.execute(stmt)).scalars().all())
    if not rows:
        return list(STAFF_DEFAULTS)
    if outlet_id is not None:
        return sorted({r.permission for r in rows if r.granted})
    # No venue in path: union of every outlet they were granted, else defaults.
    granted = {r.permission for r in rows if r.granted}
    return sorted(granted) if granted else list(STAFF_DEFAULTS)


async def assert_permission(
    db: AsyncSession,
    owner,
    permission: str,
    outlet_id: Optional[UUID] = None,
) -> None:
    perms = await resolve_permissions(db, owner, outlet_id)
    if permission not in perms:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=PERM_DENIED_MESSAGE)


def filter_staff_grants(grants: Iterable[str]) -> list[str]:
    allowed = set(STAFF_ASSIGNABLE)
    return [c for c in grants if c in allowed]
