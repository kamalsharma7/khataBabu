from __future__ import annotations

from redis.asyncio import ConnectionPool, Redis

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_pool: ConnectionPool | None = None
_client: Redis | None = None


def get_redis() -> Redis | None:
    return _client


async def init_redis(settings: Settings) -> None:
    global _pool, _client
    if not settings.redis_enabled:
        logger.info("redis_disabled")
        return

    _pool = ConnectionPool.from_url(
        settings.redis_url,
        max_connections=settings.redis_max_connections,
        decode_responses=True,
    )
    _client = Redis(connection_pool=_pool)
    await _client.ping()
    logger.info("redis_connected", url=settings.redis_url)


async def close_redis() -> None:
    global _pool, _client
    if _client is not None:
        await _client.aclose()
        _client = None
    if _pool is not None:
        await _pool.aclose()
        _pool = None
        logger.info("redis_closed")


async def check_redis_connection() -> bool:
    if _client is None:
        return True
    try:
        return await _client.ping()
    except Exception:
        logger.exception("redis_health_check_failed")
        return False
