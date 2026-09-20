from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import FoodType


class MenuCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    sort_order: int = 0


class MenuCategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    sort_order: Optional[int] = None


class MenuCategoryResponse(BaseModel):
    id: UUID
    outlet_id: UUID
    name: str
    sort_order: int

    model_config = {"from_attributes": True}


class MenuVariationInput(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    price: Decimal = Field(ge=0)
    sort_order: int = 0
    is_default: bool = False


class MenuAddonInput(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    price: Decimal = Field(ge=0)
    sort_order: int = 0
    is_available: bool = True


class MenuVariationResponse(BaseModel):
    id: UUID
    name: str
    price: Decimal
    sort_order: int
    is_default: bool

    model_config = {"from_attributes": True}


class MenuAddonResponse(BaseModel):
    id: UUID
    name: str
    price: Decimal
    sort_order: int
    is_available: bool

    model_config = {"from_attributes": True}


class MenuItemCreate(BaseModel):
    category_id: UUID
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    price: Decimal = Field(ge=0)
    short_code: Optional[str] = Field(default=None, max_length=32)
    is_veg: bool = True
    food_type: Optional[FoodType] = None
    is_available: bool = True
    sort_order: int = 0
    variations: list[MenuVariationInput] = Field(default_factory=list)
    addons: list[MenuAddonInput] = Field(default_factory=list)


class MenuItemUpdate(BaseModel):
    category_id: Optional[UUID] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(default=None, ge=0)
    short_code: Optional[str] = Field(default=None, max_length=32)
    is_veg: Optional[bool] = None
    food_type: Optional[FoodType] = None
    is_available: Optional[bool] = None
    sort_order: Optional[int] = None


class MenuItemModifiersUpdate(BaseModel):
    variations: list[MenuVariationInput] = Field(default_factory=list)
    addons: list[MenuAddonInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def default_variation_when_present(self) -> "MenuItemModifiersUpdate":
        if self.variations and not any(v.is_default for v in self.variations):
            self.variations[0].is_default = True
        return self


class MenuItemResponse(BaseModel):
    id: UUID
    outlet_id: UUID
    category_id: UUID
    name: str
    description: Optional[str]
    price: Decimal
    short_code: Optional[str]
    is_veg: bool
    food_type: FoodType
    is_available: bool
    sort_order: int
    variations: list[MenuVariationResponse] = Field(default_factory=list)
    addons: list[MenuAddonResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}
