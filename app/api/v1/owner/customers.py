import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.owner import get_current_owner
from app.api.deps.permissions import require_permission
from app.db.deps import get_db
from app.models.tenant import BusinessOwner
from app.schemas.owner.customer import (
    SEGMENT_PATTERN,
    SORT_PATTERN,
    CrmInsightsResponse,
    CustomerBackfillResponse,
    CustomerCreate,
    CustomerDetail,
    CustomerListResponse,
    CustomerLookupResponse,
    CustomerSummary,
    CustomerUpdate,
)
from app.services.owner.customer_service import OwnerCustomerService
from app.services.owner.permissions import PERM_ANALYTICS, PERM_POS_BILLING

router = APIRouter(prefix="/outlets/{outlet_id}/customers", tags=["owner-customers"])

# Billing staff need lookup / search / create / update while taking orders;
# the full database, insights and deletes are for owners/admins (analytics permission).
billing = Depends(require_permission(PERM_POS_BILLING))
crm = Depends(require_permission(PERM_ANALYTICS))


@router.get("/lookup", response_model=CustomerLookupResponse, dependencies=[billing])
async def lookup_customer(
    outlet_id: uuid.UUID,
    phone: str = Query(min_length=4, max_length=20),
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> CustomerLookupResponse:
    return await OwnerCustomerService(db).lookup(owner, outlet_id, phone)


@router.get("/search", response_model=list[CustomerSummary], dependencies=[billing])
async def search_customers(
    outlet_id: uuid.UUID,
    q: str = Query(min_length=1, max_length=64),
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> list[CustomerSummary]:
    return await OwnerCustomerService(db).search(owner, outlet_id, q)


@router.get("/insights", response_model=CrmInsightsResponse, dependencies=[crm])
async def crm_insights(
    outlet_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> CrmInsightsResponse:
    return await OwnerCustomerService(db).insights(owner, outlet_id)


@router.post("/backfill", response_model=CustomerBackfillResponse, dependencies=[crm])
async def backfill_customers(
    outlet_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> CustomerBackfillResponse:
    return await OwnerCustomerService(db).backfill(owner, outlet_id)


@router.get("", response_model=CustomerListResponse, dependencies=[crm])
async def list_customers(
    outlet_id: uuid.UUID,
    q: Optional[str] = Query(default=None, max_length=64),
    segment: Optional[str] = Query(default=None, pattern=SEGMENT_PATTERN),
    sort: Optional[str] = Query(default=None, pattern=SORT_PATTERN),
    tag: Optional[str] = Query(default=None, max_length=32),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> CustomerListResponse:
    return await OwnerCustomerService(db).list_customers(owner, outlet_id, q, segment, sort, tag, limit, offset)


@router.post("", response_model=CustomerDetail, status_code=status.HTTP_201_CREATED, dependencies=[billing])
async def create_customer(
    outlet_id: uuid.UUID,
    body: CustomerCreate,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> CustomerDetail:
    return await OwnerCustomerService(db).create_customer(owner, outlet_id, body)


@router.get("/{customer_id}", response_model=CustomerDetail, dependencies=[billing])
async def get_customer(
    outlet_id: uuid.UUID,
    customer_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> CustomerDetail:
    return await OwnerCustomerService(db).get_customer(owner, outlet_id, customer_id)


@router.patch("/{customer_id}", response_model=CustomerDetail, dependencies=[billing])
async def update_customer(
    outlet_id: uuid.UUID,
    customer_id: uuid.UUID,
    body: CustomerUpdate,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> CustomerDetail:
    return await OwnerCustomerService(db).update_customer(owner, outlet_id, customer_id, body)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[crm])
async def delete_customer(
    outlet_id: uuid.UUID,
    customer_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> None:
    await OwnerCustomerService(db).delete_customer(owner, outlet_id, customer_id)
