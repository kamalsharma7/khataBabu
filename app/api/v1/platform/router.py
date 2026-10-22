from fastapi import APIRouter

from app.api.v1.platform import auth, collections, employees, expenditures, onboarding, territory

platform_router = APIRouter(prefix="/platform", tags=["platform"])

platform_router.include_router(auth.router, prefix="/auth")
platform_router.include_router(onboarding.router, prefix="/onboarding")
platform_router.include_router(employees.router, prefix="/employees")
platform_router.include_router(expenditures.router, prefix="/expenditures")
platform_router.include_router(territory.router, prefix="/territory")
platform_router.include_router(collections.router, prefix="/collections")
