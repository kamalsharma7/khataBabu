from __future__ import annotations

import uuid
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.core.security import decode_owner_access_token
from app.db.deps import get_db
from app.models.tenant import BusinessOwner

_bearer = HTTPBearer(auto_error=False)


async def get_current_owner(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> BusinessOwner:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_owner_access_token(settings, credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "owner_access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    try:
        owner_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")

    result = await db.execute(
        select(BusinessOwner)
        .where(BusinessOwner.id == owner_id)
        .options(selectinload(BusinessOwner.business)),
    )
    owner = result.scalar_one_or_none()
    if owner is None or not owner.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Owner inactive")

    return owner
