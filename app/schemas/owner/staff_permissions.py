from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PermissionItem(BaseModel):
    code: str
    label: str
    hint: str
    staff_assignable: bool
    default_staff: bool
    dangerous: bool = False


class PermissionGroup(BaseModel):
    id: str
    label: str
    staff_assignable: bool
    permissions: list[PermissionItem]


class StaffMemberSummary(BaseModel):
    id: UUID
    full_name: str
    username: str
    role: str
    is_active: bool


class StaffGrantRow(StaffMemberSummary):
    configured: bool
    grants: dict[str, bool]


class StaffPermissionMatrix(BaseModel):
    outlet_id: UUID
    outlet_name: str
    catalog: list[PermissionGroup]
    managers: list[StaffMemberSummary]
    staff: list[StaffGrantRow]


class StaffPermissionSaveBody(BaseModel):
    grants: dict[str, bool] = Field(default_factory=dict)
    apply_to_all_outlets: bool = False


class MyPermissionsResponse(BaseModel):
    outlet_id: Optional[UUID] = None
    role: str
    can_manage_permissions: bool
    source: str
    permissions: list[str]
