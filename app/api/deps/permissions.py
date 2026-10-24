from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.owner import get_current_owner
from app.db.deps import get_db
from app.models.tenant import BusinessOwner
from app.services.owner.permissions import (
    PERM_DENIED_MESSAGE,
    has_permission,
    permissions_for_role,
    resolve_permissions,
)


def _outlet_id_from_request(request: Request) -> UUID | None:
    raw = request.path_params.get("outlet_id")
    if not raw:
        return None
    try:
        return UUID(str(raw))
    except ValueError:
        return None


def require_permission(permission: str) -> Callable:
    async def _checker(
        request: Request,
        owner: BusinessOwner = Depends(get_current_owner),
        db: AsyncSession = Depends(get_db),
    ) -> BusinessOwner:
        outlet_id = _outlet_id_from_request(request)
        perms = await resolve_permissions(db, owner, outlet_id)
        if permission not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=PERM_DENIED_MESSAGE)
        return owner

    return _checker


def require_any_permission(*permissions: str) -> Callable:
    async def _checker(
        request: Request,
        owner: BusinessOwner = Depends(get_current_owner),
        db: AsyncSession = Depends(get_db),
    ) -> BusinessOwner:
        outlet_id = _outlet_id_from_request(request)
        perms = await resolve_permissions(db, owner, outlet_id)
        if not any(p in perms for p in permissions):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=PERM_DENIED_MESSAGE)
        return owner

    return _checker


__all__ = [
    "require_permission",
    "require_any_permission",
    "has_permission",
    "permissions_for_role",
]
