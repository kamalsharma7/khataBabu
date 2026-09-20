from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.core.config import Settings, get_settings
from app.core.logging import get_logger, setup_logging
from app.db.session import close_db, init_db
from app.integrations.kafka import close_kafka, init_kafka
from app.integrations.redis import close_redis, init_redis

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = get_settings()
    setup_logging(settings)
    logger.info(
        "application_starting",
        app_name=settings.app_name,
        env=settings.app_env,
    )

    await init_db(settings)
    await init_redis(settings)
    await init_kafka(settings)

    yield

    await close_kafka()
    await close_redis()
    await close_db()
    logger.info("application_stopped")
