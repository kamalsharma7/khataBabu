from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import Settings

_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=2,
    hash_len=32,
    salt_len=16,
)


def hash_password(plain_password: str) -> str:
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, plain_password)
    except VerifyMismatchError:
        return False


def needs_rehash(password_hash: str) -> bool:
    return _password_hasher.check_needs_rehash(password_hash)


def generate_secure_password(length: int = 16) -> str:
    """Cryptographically secure temporary password (alphanumeric, no ambiguous chars)."""
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_otp(length: int = 6) -> str:
    upper = 10**length
    return str(secrets.randbelow(upper)).zfill(length)


def hash_otp(otp: str, session_id: UUID, pepper: str) -> str:
    payload = f"{otp}:{session_id}:{pepper}".encode()
    return hashlib.sha256(payload).hexdigest()


def verify_otp(otp: str, session_id: UUID, pepper: str, expected_hash: str) -> bool:
    computed = hash_otp(otp, session_id, pepper)
    return hmac.compare_digest(computed, expected_hash)


def create_platform_access_token(
    settings: Settings,
    admin_id: UUID,
    *,
    extra_claims: Optional[dict[str, Any]] = None,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.platform_access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(admin_id),
        "aud": settings.platform_jwt_audience,
        "type": "platform_access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(
        payload,
        settings.platform_jwt_secret,
        algorithm=settings.platform_jwt_algorithm,
    )


def decode_platform_access_token(settings: Settings, token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.platform_jwt_secret,
        algorithms=[settings.platform_jwt_algorithm],
        audience=settings.platform_jwt_audience,
        options={"require": ["exp", "iat", "sub", "aud", "type"]},
    )


def create_owner_access_token(
    settings: Settings,
    owner_id: UUID,
    business_id: UUID,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.owner_access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(owner_id),
        "business_id": str(business_id),
        "aud": settings.owner_jwt_audience,
        "type": "owner_access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(
        payload,
        settings.owner_jwt_secret,
        algorithm=settings.owner_jwt_algorithm,
    )


def decode_owner_access_token(settings: Settings, token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.owner_jwt_secret,
        algorithms=[settings.owner_jwt_algorithm],
        audience=settings.owner_jwt_audience,
        options={"require": ["exp", "iat", "sub", "aud", "type", "business_id"]},
    )


def create_owner_analytics_token(
    settings: Settings,
    owner_id: UUID,
    business_id: UUID,
    outlet_id: UUID,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.owner_analytics_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(owner_id),
        "business_id": str(business_id),
        "outlet_id": str(outlet_id),
        "aud": settings.owner_jwt_audience,
        "type": "owner_analytics",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(
        payload,
        settings.owner_jwt_secret,
        algorithm=settings.owner_jwt_algorithm,
    )


def decode_owner_analytics_token(settings: Settings, token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.owner_jwt_secret,
        algorithms=[settings.owner_jwt_algorithm],
        audience=settings.owner_jwt_audience,
        options={"require": ["exp", "iat", "sub", "aud", "type", "business_id", "outlet_id"]},
    )
