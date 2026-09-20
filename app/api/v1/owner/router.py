from fastapi import APIRouter

from app.api.v1.owner import auth, menu, outlets, pos, venue

owner_router = APIRouter(prefix="/owner", tags=["owner"])

owner_router.include_router(auth.router, prefix="/auth")
owner_router.include_router(outlets.router, prefix="/outlets")
owner_router.include_router(venue.router)
owner_router.include_router(menu.router)
owner_router.include_router(pos.router)
