from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.owner import get_current_owner
from app.db.deps import get_db
from app.models.enums import BillStatus, OrderStatus
from app.models.tenant import BusinessOwner
from app.schemas.owner.order import (
    AddBillPaymentRequest,
    BillDetailResponse,
    BillListEntryResponse,
    BillPreviewRequest,
    BillResponse,
    FloorStatusResponse,
    KotResponse,
    OrderCancel,
    OrderCreate,
    OpenOrderLineCreate,
    OrderLineCreate,
    OrderLineUpdate,
    OrderResponse,
    OrderTransferTable,
    OrderUpdate,
    SendKotRequest,
    SettleBillRequest,
    PosBillingSettingsResponse,
    SplitBillPreviewBody,
    SplitBillPreviewResponse,
)
from app.services.owner.order_service import OwnerOrderService

router = APIRouter(prefix="/outlets/{outlet_id}/pos", tags=["owner-pos"])


@router.get("/billing-settings", response_model=PosBillingSettingsResponse)
async def pos_billing_settings(
    outlet_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> PosBillingSettingsResponse:
    service = OwnerOrderService(db)
    return await service.billing_settings(owner, outlet_id)


@router.get("/bills", response_model=list[BillListEntryResponse])
async def list_bills(
    outlet_id: uuid.UUID,
    bill_status: Optional[BillStatus] = Query(default=BillStatus.SETTLED),
    limit: int = Query(default=200, ge=1, le=500),
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> list[BillListEntryResponse]:
    service = OwnerOrderService(db)
    return await service.list_bills(owner, outlet_id, bill_status, limit)


@router.get("/bills/{bill_id}/detail", response_model=BillDetailResponse)
async def get_bill_detail(
    outlet_id: uuid.UUID,
    bill_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> BillDetailResponse:
    service = OwnerOrderService(db)
    return await service.get_bill_detail(owner, outlet_id, bill_id)


@router.get("/floor", response_model=FloorStatusResponse)
async def pos_floor(
    outlet_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> FloorStatusResponse:
    service = OwnerOrderService(db)
    return await service.floor_status(owner, outlet_id)


@router.get("/orders", response_model=list[OrderResponse])
async def list_orders(
    outlet_id: uuid.UUID,
    order_status: Optional[OrderStatus] = Query(default=OrderStatus.OPEN),
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> list[OrderResponse]:
    service = OwnerOrderService(db)
    return await service.list_orders(owner, outlet_id, order_status)


@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    outlet_id: uuid.UUID,
    body: OrderCreate,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    service = OwnerOrderService(db)
    return await service.create_order(owner, outlet_id, body)


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    outlet_id: uuid.UUID,
    order_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    service = OwnerOrderService(db)
    return await service.get_order(owner, outlet_id, order_id)


@router.patch("/orders/{order_id}", response_model=OrderResponse)
async def update_order(
    outlet_id: uuid.UUID,
    order_id: uuid.UUID,
    body: OrderUpdate,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    service = OwnerOrderService(db)
    return await service.update_order(owner, outlet_id, order_id, body)


@router.post("/orders/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    outlet_id: uuid.UUID,
    order_id: uuid.UUID,
    body: OrderCancel,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    service = OwnerOrderService(db)
    return await service.cancel_order(owner, outlet_id, order_id, body.reason)


@router.post("/orders/{order_id}/transfer-table", response_model=OrderResponse)
async def transfer_table(
    outlet_id: uuid.UUID,
    order_id: uuid.UUID,
    body: OrderTransferTable,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    service = OwnerOrderService(db)
    return await service.transfer_table(owner, outlet_id, order_id, body)


@router.post("/orders/{order_id}/lines", response_model=OrderResponse)
async def add_order_line(
    outlet_id: uuid.UUID,
    order_id: uuid.UUID,
    body: OrderLineCreate,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    service = OwnerOrderService(db)
    return await service.add_line(owner, outlet_id, order_id, body)


@router.post("/orders/{order_id}/open-lines", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def add_open_order_line(
    outlet_id: uuid.UUID,
    order_id: uuid.UUID,
    body: OpenOrderLineCreate,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    service = OwnerOrderService(db)
    return await service.add_open_line(owner, outlet_id, order_id, body)


@router.patch("/orders/{order_id}/lines/{line_id}", response_model=OrderResponse)
async def update_order_line(
    outlet_id: uuid.UUID,
    order_id: uuid.UUID,
    line_id: uuid.UUID,
    body: OrderLineUpdate,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    service = OwnerOrderService(db)
    return await service.update_line(owner, outlet_id, order_id, line_id, body)


@router.delete("/orders/{order_id}/lines/{line_id}", response_model=OrderResponse)
async def remove_order_line(
    outlet_id: uuid.UUID,
    order_id: uuid.UUID,
    line_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    service = OwnerOrderService(db)
    return await service.remove_line(owner, outlet_id, order_id, line_id)


@router.post("/orders/{order_id}/lines/{line_id}/cancel", response_model=OrderResponse)
async def cancel_order_line(
    outlet_id: uuid.UUID,
    order_id: uuid.UUID,
    line_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    service = OwnerOrderService(db)
    return await service.cancel_line(owner, outlet_id, order_id, line_id)


@router.post("/orders/{order_id}/kot", response_model=KotResponse, status_code=status.HTTP_201_CREATED)
async def send_kot(
    outlet_id: uuid.UUID,
    order_id: uuid.UUID,
    body: SendKotRequest,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> KotResponse:
    service = OwnerOrderService(db)
    return await service.send_kot(owner, outlet_id, order_id, body)


@router.get("/orders/{order_id}/kots", response_model=list[KotResponse])
async def list_order_kots(
    outlet_id: uuid.UUID,
    order_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> list[KotResponse]:
    service = OwnerOrderService(db)
    return await service.list_kots_for_order(owner, outlet_id, order_id)


@router.get("/kots/{kot_id}", response_model=KotResponse)
async def get_kot(
    outlet_id: uuid.UUID,
    kot_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> KotResponse:
    service = OwnerOrderService(db)
    return await service.get_kot(owner, outlet_id, kot_id)


@router.post("/orders/{order_id}/bill", response_model=BillResponse)
async def create_bill(
    outlet_id: uuid.UUID,
    order_id: uuid.UUID,
    body: BillPreviewRequest,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> BillResponse:
    service = OwnerOrderService(db)
    return await service.create_or_refresh_bill(owner, outlet_id, order_id, body)


@router.get("/orders/{order_id}/bill", response_model=BillResponse)
async def get_order_bill(
    outlet_id: uuid.UUID,
    order_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> BillResponse:
    service = OwnerOrderService(db)
    return await service.get_bill_for_order(owner, outlet_id, order_id)


@router.post("/bills/{bill_id}/payments", response_model=BillResponse)
async def add_bill_payment(
    outlet_id: uuid.UUID,
    bill_id: uuid.UUID,
    body: AddBillPaymentRequest,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> BillResponse:
    service = OwnerOrderService(db)
    return await service.add_bill_payment(owner, outlet_id, bill_id, body)


@router.post("/orders/{order_id}/bill/split-preview", response_model=SplitBillPreviewResponse)
async def split_bill_preview(
    outlet_id: uuid.UUID,
    order_id: uuid.UUID,
    body: SplitBillPreviewBody,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> SplitBillPreviewResponse:
    service = OwnerOrderService(db)
    return await service.split_bill_preview(owner, outlet_id, order_id, body)


@router.post("/bills/{bill_id}/settle", response_model=BillResponse)
async def settle_bill(
    outlet_id: uuid.UUID,
    bill_id: uuid.UUID,
    body: SettleBillRequest,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> BillResponse:
    service = OwnerOrderService(db)
    return await service.settle_bill(owner, outlet_id, bill_id, body)
