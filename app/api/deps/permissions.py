from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.api.deps.owner import get_current_owner
from app.models.tenant import BusinessOwner
from app.services.owner.permissions import has_permission, permissions_for_role


def require_permission(permission: str) -> Callable:
    async def _checker(owner: BusinessOwner = Depends(get_current_owner)) -> BusinessOwner:
        if not has_permission(owner.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You do not have permission for this action ({permission}).",
            )
        return owner

    return _checker


def require_any_permission(*permissions: str) -> Callable:
    async def _checker(owner: BusinessOwner = Depends(get_current_owner)) -> BusinessOwner:
        perms = permissions_for_role(owner.role)
        if not any(p in perms for p in permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission for this action.",
            )
        return owner

    return _checker
