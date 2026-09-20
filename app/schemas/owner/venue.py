from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.venue import ResourceKind


class AreaCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    sort_order: int = 0
    initial_table_count: Optional[int] = Field(
        default=None,
        ge=0,
        le=500,
        description="If set, create this many dine tables named '{prefix} 1', '{prefix} 2', …",
    )
    table_label_prefix: str = Field(default="Table", min_length=1, max_length=32)


class TableBulkCreate(BaseModel):
    count: int = Field(ge=1, le=500)
    table_label_prefix: str = Field(default="Table", min_length=1, max_length=32)
    start_number: int = Field(default=1, ge=1, le=9999)


class AreaUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    sort_order: Optional[int] = None


class AreaResponse(BaseModel):
    id: UUID
    outlet_id: UUID
    name: str
    sort_order: int

    model_config = {"from_attributes": True}


class TableCreate(BaseModel):
    label: str = Field(min_length=1, max_length=64)
    capacity: Optional[int] = Field(default=None, ge=1, le=99)
    resource_kind: ResourceKind = ResourceKind.DINE_TABLE
    hourly_rate: Optional[Decimal] = Field(default=None, ge=0)
    sort_order: int = 0


class TableUpdate(BaseModel):
    label: Optional[str] = Field(default=None, min_length=1, max_length=64)
    capacity: Optional[int] = Field(default=None, ge=1, le=99)
    resource_kind: Optional[ResourceKind] = None
    hourly_rate: Optional[Decimal] = Field(default=None, ge=0)
    sort_order: Optional[int] = None
    area_id: Optional[UUID] = None


class TableResponse(BaseModel):
    id: UUID
    outlet_id: UUID
    area_id: UUID
    label: str
    capacity: Optional[int]
    resource_kind: ResourceKind
    hourly_rate: Optional[Decimal]
    sort_order: int

    model_config = {"from_attributes": True}
