from __future__ import annotations

import uuid
from typing import Optional

from fastapi import Depends, Header, HTTPException, status

from app.api.deps.owner import get_current_owner
from app.core.config import Settings, get_settings
from app.core.security import decode_owner_analytics_token
from app.models.tenant import BusinessOwner


async def require_analytics_unlock(
    outlet_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    analytics_header: Optional[str] = Header(default=None, alias="X-Analytics-Token"),
    settings: Settings = Depends(get_settings),
) -> BusinessOwner:
    # Overview token must NOT be read from Authorization — that header carries the owner session JWT.
    token: Optional[str] = None
    if analytics_header:
        token = analytics_header.strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Overview is locked. Enter your overview PIN.",
        )

    try:
        payload = decode_owner_analytics_token(settings, token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Overview session expired. Unlock again.",
        )

    if payload.get("type") != "owner_analytics":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid overview token")

    try:
        if uuid.UUID(payload["sub"]) != owner.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid overview token")
        if uuid.UUID(payload["outlet_id"]) != outlet_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid overview token")
    except (KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid overview token")

    return owner
