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
    price: Decimal = Field(default=Decimal("0"), ge=0)
    sort_order: int = 0
    is_default: bool = False
    is_available: bool = True
    weight_grams: int | None = Field(default=None, ge=1, le=50000)
    food_type: FoodType | None = Field(
        default=None,
        description="Null = same as menu item",
    )
    children: list["MenuVariationInput"] = Field(default_factory=list)


class MenuAddonInput(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    price: Decimal = Field(ge=0)
    sort_order: int = 0
    is_available: bool = True
    weight_grams: int | None = Field(default=None, ge=1, le=50000)
    food_type: FoodType | None = Field(
        default=None,
        description="Null = same as menu item; non-veg topping can mark line non-veg",
    )


class MenuAddonGroupInput(BaseModel):
    name: str = Field(default="Toppings", min_length=1, max_length=128)
    min_select: int = Field(default=0, ge=0, le=20)
    max_select: Optional[int] = Field(default=None, ge=1, le=40)
    sort_order: int = 0
    addons: list[MenuAddonInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def max_gte_min(self) -> "MenuAddonGroupInput":
        if self.max_select is not None and self.max_select < self.min_select:
            raise ValueError("max_select cannot be less than min_select")
        return self


class MenuVariationResponse(BaseModel):
    id: UUID
    name: str
    price: Decimal
    sort_order: int
    is_default: bool
    is_available: bool = True
    weight_grams: int | None = None
    food_type: FoodType | None = None
    parent_id: UUID | None = None
    children: list["MenuVariationResponse"] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class MenuAddonResponse(BaseModel):
    id: UUID
    name: str
    price: Decimal
    sort_order: int
    is_available: bool
    weight_grams: int | None = None
    food_type: FoodType | None = None
    group_id: UUID | None = None

    model_config = {"from_attributes": True}


class MenuAddonGroupResponse(BaseModel):
    id: UUID
    name: str
    min_select: int = 0
    max_select: Optional[int] = None
    sort_order: int = 0
    addons: list[MenuAddonResponse] = Field(default_factory=list)

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
    gst_applicable: bool = False
    cgst_percent: Decimal = Field(default=Decimal("2.5"), ge=0, le=28)
    sgst_percent: Decimal = Field(default=Decimal("2.5"), ge=0, le=28)
    variations: list[MenuVariationInput] = Field(default_factory=list)
    addons: list[MenuAddonInput] = Field(default_factory=list)
    addon_groups: list[MenuAddonGroupInput] = Field(default_factory=list)


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
    gst_applicable: Optional[bool] = None
    cgst_percent: Optional[Decimal] = Field(default=None, ge=0, le=28)
    sgst_percent: Optional[Decimal] = Field(default=None, ge=0, le=28)


class MenuItemModifiersUpdate(BaseModel):
    variations: list[MenuVariationInput] = Field(default_factory=list)
    addons: list[MenuAddonInput] = Field(default_factory=list)
    addon_groups: list[MenuAddonGroupInput] = Field(default_factory=list)


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
    gst_applicable: bool = False
    cgst_percent: Decimal = Decimal("0")
    sgst_percent: Decimal = Decimal("0")
    variations: list[MenuVariationResponse] = Field(default_factory=list)
    addons: list[MenuAddonResponse] = Field(default_factory=list)
    addon_groups: list[MenuAddonGroupResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}
