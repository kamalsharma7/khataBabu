from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.venue import AreaBillingMode, ResourceKind


def _parse_hhmm(value: str) -> str:
    parts = value.strip().split(":")
    if len(parts) != 2:
        raise ValueError("Use HH:MM format")
    hour, minute = int(parts[0]), int(parts[1])
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError("Invalid time")
    return f"{hour:02d}:{minute:02d}"


class AreaCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    sort_order: int = 0
    billing_mode: AreaBillingMode = AreaBillingMode.DINE_IN
    operating_start: Optional[str] = Field(
        default=None,
        description="Area operating window start (HH:MM), for time-based areas",
    )
    operating_end: Optional[str] = Field(default=None, description="Area operating window end (HH:MM)")
    hourly_rate: Optional[Decimal] = Field(default=None, ge=0)
    initial_table_count: Optional[int] = Field(
        default=None,
        ge=0,
        le=500,
        description="If set, create this many dine tables named '{prefix} 1', '{prefix} 2', …",
    )
    table_label_prefix: str = Field(default="Table", min_length=1, max_length=32)

    @field_validator("operating_start", "operating_end")
    @classmethod
    def validate_time(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not str(value).strip():
            return None
        return _parse_hhmm(str(value))


class TableBulkCreate(BaseModel):
    count: int = Field(ge=1, le=500)
    table_label_prefix: str = Field(default="Table", min_length=1, max_length=32)
    start_number: int = Field(default=1, ge=1, le=9999)


class AreaUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    sort_order: Optional[int] = None
    billing_mode: Optional[AreaBillingMode] = None
    operating_start: Optional[str] = None
    operating_end: Optional[str] = None
    hourly_rate: Optional[Decimal] = Field(default=None, ge=0)

    @field_validator("operating_start", "operating_end")
    @classmethod
    def validate_time(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not str(value).strip():
            return None
        return _parse_hhmm(str(value))


class AreaResponse(BaseModel):
    id: UUID
    outlet_id: UUID
    name: str
    sort_order: int
    billing_mode: AreaBillingMode
    operating_start: Optional[str] = None
    operating_end: Optional[str] = None
    hourly_rate: Optional[Decimal] = None

    model_config = {"from_attributes": True}

    @field_validator("operating_start", "operating_end", mode="before")
    @classmethod
    def time_to_str(cls, value: object) -> Optional[str]:
        if value is None:
            return None
        if hasattr(value, "hour") and hasattr(value, "minute"):
            return f"{value.hour:02d}:{value.minute:02d}"
        return str(value)


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
