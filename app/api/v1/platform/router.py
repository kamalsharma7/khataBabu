from fastapi import APIRouter

from app.api.v1.platform import auth, onboarding

platform_router = APIRouter(prefix="/platform", tags=["platform"])

platform_router.include_router(auth.router, prefix="/auth")
platform_router.include_router(onboarding.router, prefix="/onboarding")
