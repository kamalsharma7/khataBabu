"""Owner-managed venue-wise staff permission matrix."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.staff_permission import StaffPermissionGrant
from app.models.tenant import BusinessOwner, Outlet
from app.schemas.owner.staff_permissions import (
    MyPermissionsResponse,
    StaffGrantRow,
    StaffMemberSummary,
    StaffPermissionMatrix,
    StaffPermissionSaveBody,
)
from app.services.owner.access import get_outlet_for_owner
from app.services.owner.audit_service import TenantAuditService
from app.services.owner.permissions import (
    PERM_DENIED_MESSAGE,
    STAFF_ASSIGNABLE,
    STAFF_DEFAULTS,
    catalog_groups,
    is_manager,
    is_staff,
    resolve_permissions,
)


class OwnerStaffPermissionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def my_permissions(
        self,
        owner: BusinessOwner,
        outlet_id: Optional[uuid.UUID],
    ) -> MyPermissionsResponse:
        if outlet_id is not None:
            await get_outlet_for_owner(self.db, owner, outlet_id)
        perms = await resolve_permissions(self.db, owner, outlet_id)
        source = "role"
        if is_staff(owner.role):
            configured = False
            if outlet_id is not None:
                configured = await self._has_rows(outlet_id, owner.id)
            source = "custom" if configured else "defaults"
        return MyPermissionsResponse(
            outlet_id=outlet_id,
            role=owner.role.value,
            can_manage_permissions=is_manager(owner.role),
            source=source,
            permissions=perms,
        )

    async def matrix(self, owner: BusinessOwner, outlet_id: uuid.UUID) -> StaffPermissionMatrix:
        if not is_manager(owner.role):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=PERM_DENIED_MESSAGE)
        outlet = await get_outlet_for_owner(self.db, owner, outlet_id)
        members = list(
            (
                await self.db.execute(
                    select(BusinessOwner)
                    .where(BusinessOwner.business_id == owner.business_id)
                    .order_by(BusinessOwner.created_at.asc()),
                )
            ).scalars().all(),
        )
        managers = [
            StaffMemberSummary(
                id=m.id,
                full_name=m.full_name,
                username=m.username,
                role=m.role.value,
                is_active=m.is_active,
            )
            for m in members
            if is_manager(m.role)
        ]
        staff_rows: list[StaffGrantRow] = []
        for m in members:
            if not is_staff(m.role):
                continue
            rows = list(
                (
                    await self.db.execute(
                        select(StaffPermissionGrant).where(
                            StaffPermissionGrant.outlet_id == outlet_id,
                            StaffPermissionGrant.owner_id == m.id,
                        ),
                    )
                ).scalars().all(),
            )
            configured = bool(rows)
            granted = {r.permission: r.granted for r in rows} if configured else {}
            ticks = {
                code: granted.get(code, code in STAFF_DEFAULTS if not configured else False)
                for code in STAFF_ASSIGNABLE
            }
            staff_rows.append(
                StaffGrantRow(
                    id=m.id,
                    full_name=m.full_name,
                    username=m.username,
                    role=m.role.value,
                    is_active=m.is_active,
                    configured=configured,
                    grants=ticks,
                ),
            )
        return StaffPermissionMatrix(
            outlet_id=outlet.id,
            outlet_name=outlet.name,
            catalog=catalog_groups(),
            managers=managers,
            staff=staff_rows,
        )

    async def save(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        staff_id: uuid.UUID,
        payload: StaffPermissionSaveBody,
    ) -> StaffPermissionMatrix:
        if not is_manager(owner.role):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=PERM_DENIED_MESSAGE)
        outlet = await get_outlet_for_owner(self.db, owner, outlet_id)
        staff = await self.db.get(BusinessOwner, staff_id)
        if staff is None or staff.business_id != owner.business_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff login not found")
        if not is_staff(staff.role):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Owner / admin access cannot be limited from this screen",
            )

        targets = [outlet.id]
        if payload.apply_to_all_outlets:
            all_outlets = list(
                (
                    await self.db.execute(select(Outlet.id).where(Outlet.business_id == owner.business_id))
                ).scalars().all(),
            )
            targets = list(all_outlets)

        for oid in targets:
            await self._replace_grants(oid, staff.id, owner.id, payload.grants)

        enabled = [c for c in STAFF_ASSIGNABLE if payload.grants.get(c)]
        await TenantAuditService(self.db).log(
            business_id=owner.business_id,
            outlet_id=outlet.id,
            actor=owner,
            action="staff.permissions",
            entity_type="staff",
            entity_id=str(staff.id),
            summary=f"Updated permissions for {staff.full_name} at {outlet.name}",
            detail={
                "staff_username": staff.username,
                "enabled": enabled,
                "apply_to_all_outlets": payload.apply_to_all_outlets,
            },
        )
        await self.db.commit()
        return await self.matrix(owner, outlet_id)

    async def _replace_grants(
        self,
        outlet_id: uuid.UUID,
        staff_id: uuid.UUID,
        actor_id: uuid.UUID,
        grants: dict[str, bool],
    ) -> None:
        existing = list(
            (
                await self.db.execute(
                    select(StaffPermissionGrant).where(
                        StaffPermissionGrant.outlet_id == outlet_id,
                        StaffPermissionGrant.owner_id == staff_id,
                    ),
                )
            ).scalars().all(),
        )
        by_code = {r.permission: r for r in existing}
        for code in STAFF_ASSIGNABLE:
            granted = bool(grants.get(code, False))
            row = by_code.get(code)
            if row is None:
                self.db.add(
                    StaffPermissionGrant(
                        outlet_id=outlet_id,
                        owner_id=staff_id,
                        permission=code,
                        granted=granted,
                        updated_by_owner_id=actor_id,
                    ),
                )
            else:
                row.granted = granted
                row.updated_by_owner_id = actor_id
        # Drop unknown leftover codes from older catalogs.
        for code, row in by_code.items():
            if code not in STAFF_ASSIGNABLE:
                await self.db.delete(row)
        await self.db.flush()

    async def _has_rows(self, outlet_id: uuid.UUID, owner_id: uuid.UUID) -> bool:
        row = (
            await self.db.execute(
                select(StaffPermissionGrant.id)
                .where(
                    StaffPermissionGrant.outlet_id == outlet_id,
                    StaffPermissionGrant.owner_id == owner_id,
                )
                .limit(1),
            )
        ).scalar_one_or_none()
        return row is not None
