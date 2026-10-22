from fastapi import APIRouter

from app.api.v1.owner import (
    analytics,
    auth,
    compliance,
    customers,
    inventory,
    menu,
    outlets,
    pos,
    purchases,
    settings,
    venue,
)

owner_router = APIRouter(prefix="/owner", tags=["owner"])

owner_router.include_router(auth.router, prefix="/auth")
owner_router.include_router(settings.router)
owner_router.include_router(compliance.router)
owner_router.include_router(outlets.router, prefix="/outlets")
owner_router.include_router(venue.router)
owner_router.include_router(menu.router)
owner_router.include_router(pos.router)
owner_router.include_router(inventory.router)
owner_router.include_router(purchases.router)
owner_router.include_router(customers.router)
owner_router.include_router(analytics.router)
