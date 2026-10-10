from fastapi import APIRouter

from app.api.v1.platform import auth, employees, onboarding

platform_router = APIRouter(prefix="/platform", tags=["platform"])

platform_router.include_router(auth.router, prefix="/auth")
platform_router.include_router(onboarding.router, prefix="/onboarding")
platform_router.include_router(employees.router, prefix="/employees")
