from __future__ import annotations

import enum


class BusinessType(str, enum.Enum):
    RESTAURANT = "restaurant"
    RESTAURANT_AND_SNOOKER = "restaurant_and_snooker"
    CAFE = "cafe"
    BAR = "bar"
    MULTI_VENUE = "multi_venue"
    OTHER = "other"


class TenantStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class PlanTier(str, enum.Enum):
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class OwnerRole(str, enum.Enum):
    OWNER = "owner"


class OperatingModel(str, enum.Enum):
    DINE_IN = "dine_in"
    TAKEAWAY = "takeaway"
    DELIVERY = "delivery"


class VenueKind(str, enum.Enum):
    DINING = "dining"
    SNOOKER_POOL = "snooker_pool"
    PRIVATE_ROOMS = "private_rooms"
    BANQUET = "banquet"
    BAR = "bar"
    GAMING = "gaming"
    OTHER = "other"


class OrderType(str, enum.Enum):
    DINE_IN = "dine_in"
    TAKEAWAY = "takeaway"
    DELIVERY = "delivery"


class OrderStatus(str, enum.Enum):
    OPEN = "open"
    SETTLED = "settled"
    CANCELLED = "cancelled"


class OrderLineStatus(str, enum.Enum):
    PENDING_KOT = "pending_kot"
    IN_KOT = "in_kot"
    SERVED = "served"
    CANCELLED = "cancelled"


class KotStatus(str, enum.Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"


class BillStatus(str, enum.Enum):
    OPEN = "open"
    SETTLED = "settled"
    VOID = "void"


class FoodType(str, enum.Enum):
    VEG = "veg"
    NON_VEG = "non_veg"
    EGG = "egg"


class TableVisualState(str, enum.Enum):
    BLANK = "blank"
    RUNNING = "running"
    RUNNING_KOT = "running_kot"
    PRINTED = "printed"


class PaymentMethod(str, enum.Enum):
    CASH = "cash"
    UPI = "upi"
    CARD = "card"
    WALLET = "wallet"
    BANK = "bank"
    DUE = "due"
    COMPLIMENTARY = "complimentary"
    OTHER = "other"
