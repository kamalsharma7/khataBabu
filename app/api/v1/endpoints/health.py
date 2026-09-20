from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app import __version__
from app.core.config import get_settings
from app.db.session import check_db_connection
from app.integrations.kafka import check_kafka_connection
from app.integrations.redis import check_redis_connection

router = APIRouter()


@router.get("/health/live", summary="Liveness probe")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", summary="Readiness probe")
async def readiness() -> JSONResponse:
    settings = get_settings()
    checks: dict[str, bool] = {
        "database": await check_db_connection(),
        "redis": await check_redis_connection(),
        "kafka": await check_kafka_connection(),
    }

    required_ok = checks["database"]
    if settings.redis_enabled:
        required_ok = required_ok and checks["redis"]
    if settings.kafka_enabled:
        required_ok = required_ok and checks["kafka"]

    body = {
        "status": "ready" if required_ok else "not_ready",
        "version": __version__,
        "environment": settings.app_env,
        "checks": checks,
    }
    code = status.HTTP_200_OK if required_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(content=body, status_code=code)
