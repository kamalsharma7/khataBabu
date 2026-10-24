import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.owner import get_current_owner
from app.db.deps import get_db
from app.models.tenant import BusinessOwner
from app.schemas.owner.staff_permissions import (
    MyPermissionsResponse,
    StaffPermissionMatrix,
    StaffPermissionSaveBody,
)
from app.services.owner.staff_permission_service import OwnerStaffPermissionService

router = APIRouter(tags=["owner-staff-permissions"])


@router.get("/outlets/{outlet_id}/my-permissions", response_model=MyPermissionsResponse)
async def my_outlet_permissions(
    outlet_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> MyPermissionsResponse:
    return await OwnerStaffPermissionService(db).my_permissions(owner, outlet_id)


@router.get("/my-permissions", response_model=MyPermissionsResponse)
async def my_permissions(
    outlet_id: Optional[uuid.UUID] = None,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> MyPermissionsResponse:
    return await OwnerStaffPermissionService(db).my_permissions(owner, outlet_id)


@router.get("/outlets/{outlet_id}/staff-permissions", response_model=StaffPermissionMatrix)
async def staff_permission_matrix(
    outlet_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> StaffPermissionMatrix:
    return await OwnerStaffPermissionService(db).matrix(owner, outlet_id)


@router.put("/outlets/{outlet_id}/staff-permissions/{staff_id}", response_model=StaffPermissionMatrix)
async def save_staff_permissions(
    outlet_id: uuid.UUID,
    staff_id: uuid.UUID,
    body: StaffPermissionSaveBody,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> StaffPermissionMatrix:
    return await OwnerStaffPermissionService(db).save(owner, outlet_id, staff_id, body)
