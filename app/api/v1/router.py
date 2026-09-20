from fastapi import APIRouter

from app.api.v1.endpoints import health
from app.api.v1.owner import owner_router
from app.api.v1.platform import platform_router

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(platform_router)
api_router.include_router(owner_router)
