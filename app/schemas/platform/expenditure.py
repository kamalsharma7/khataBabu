from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import PlatformExpenditureCategory


class ExpenditureCreate(BaseModel):
    category: PlatformExpenditureCategory
    amount_inr: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    title: str = Field(min_length=1, max_length=255)
    notes: str | None = Field(default=None, max_length=4000)
    spent_at: datetime | None = None
    sales_employee_id: UUID | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_sales_employee(self) -> ExpenditureCreate:
        if self.category == PlatformExpenditureCategory.SALES_TEAM_SALARY:
            if self.sales_employee_id is None:
                raise ValueError("sales_employee_id is required for sales team salary")
        elif self.sales_employee_id is not None:
            raise ValueError("sales_employee_id is only allowed for sales team salary")
        return self


class ExpenditureUpdate(BaseModel):
    amount_inr: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = Field(default=None, max_length=4000)
    spent_at: datetime | None = None
    sales_employee_id: UUID | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()


class ExpenditureResponse(BaseModel):
    id: UUID
    category: PlatformExpenditureCategory
    amount_inr: Decimal
    title: str
    notes: str | None
    spent_at: datetime
    recorded_by_admin_id: UUID | None
    sales_employee_id: UUID | None = None
    sales_employee_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CategoryTotal(BaseModel):
    category: PlatformExpenditureCategory
    total_inr: Decimal
    entry_count: int


class ExpenditureSummary(BaseModel):
    from_date: date | None
    to_date: date | None
    grand_total_inr: Decimal
    entry_count: int
    by_category: list[CategoryTotal]
