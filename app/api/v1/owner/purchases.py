import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.owner import get_current_owner
from app.api.deps.permissions import require_permission
from app.db.deps import get_db
from app.models.tenant import BusinessOwner
from app.schemas.owner.purchase import (
    PurchaseInvoiceCreate,
    PurchaseInvoiceDetail,
    PurchaseInvoiceUpdate,
    PurchaseListResponse,
    PurchasePaymentCreate,
)
from app.services.owner.permissions import PERM_POS_INVENTORY
from app.services.owner.purchase_service import OwnerPurchaseService

router = APIRouter(
    prefix="/outlets/{outlet_id}/purchases",
    tags=["owner-purchases"],
    dependencies=[Depends(require_permission(PERM_POS_INVENTORY))],
)


@router.get("", response_model=PurchaseListResponse)
async def list_purchases(
    outlet_id: uuid.UUID,
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    vendor: Optional[str] = Query(default=None, max_length=255),
    invoice_number: Optional[str] = Query(default=None, max_length=64),
    payment_status: Optional[str] = Query(default=None, pattern="^(all|unpaid|partial|paid)$"),
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> PurchaseListResponse:
    service = OwnerPurchaseService(db)
    return await service.list_invoices(
        owner, outlet_id, from_date, to_date, vendor, invoice_number, payment_status,
    )


@router.post("", response_model=PurchaseInvoiceDetail, status_code=status.HTTP_201_CREATED)
async def create_purchase(
    outlet_id: uuid.UUID,
    body: PurchaseInvoiceCreate,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> PurchaseInvoiceDetail:
    service = OwnerPurchaseService(db)
    return await service.create_invoice(owner, outlet_id, body)


@router.get("/{invoice_id}", response_model=PurchaseInvoiceDetail)
async def get_purchase(
    outlet_id: uuid.UUID,
    invoice_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> PurchaseInvoiceDetail:
    service = OwnerPurchaseService(db)
    return await service.get_invoice(owner, outlet_id, invoice_id)


@router.patch("/{invoice_id}", response_model=PurchaseInvoiceDetail)
async def update_purchase(
    outlet_id: uuid.UUID,
    invoice_id: uuid.UUID,
    body: PurchaseInvoiceUpdate,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> PurchaseInvoiceDetail:
    service = OwnerPurchaseService(db)
    return await service.update_invoice(owner, outlet_id, invoice_id, body)


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_purchase(
    outlet_id: uuid.UUID,
    invoice_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = OwnerPurchaseService(db)
    await service.delete_invoice(owner, outlet_id, invoice_id)


@router.post("/{invoice_id}/payments", response_model=PurchaseInvoiceDetail)
async def add_purchase_payment(
    outlet_id: uuid.UUID,
    invoice_id: uuid.UUID,
    body: PurchasePaymentCreate,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> PurchaseInvoiceDetail:
    service = OwnerPurchaseService(db)
    return await service.add_payment(owner, outlet_id, invoice_id, body)


@router.post("/{invoice_id}/apply-stock", response_model=PurchaseInvoiceDetail)
async def apply_purchase_stock(
    outlet_id: uuid.UUID,
    invoice_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> PurchaseInvoiceDetail:
    service = OwnerPurchaseService(db)
    return await service.apply_stock(owner, outlet_id, invoice_id)
