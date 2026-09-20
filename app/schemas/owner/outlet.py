from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class OutletSummary(BaseModel):
    id: UUID
    name: str
    ref_code: str
    status: str
    city_hint: str | None = None

    model_config = {"from_attributes": True}
