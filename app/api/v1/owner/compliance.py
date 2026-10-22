from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.owner import get_current_owner
from app.api.deps.permissions import require_permission
from app.db.deps import get_db
from app.models.tenant import BusinessOwner
from app.schemas.owner.settings import AuditLogListResponse, RefundCreateRequest, RefundResponse
from app.services.owner.compliance_query_service import ComplianceQueryService
from app.services.owner.invoice_service import InvoiceService
from app.services.owner.permissions import PERM_AUDIT_VIEW, PERM_POS_BILLS, PERM_POS_REFUND
from app.services.owner.refund_service import RefundService
from app.schemas.owner.settings import DiscountPolicyResponse
from app.services.owner.business_settings_service import BusinessSettingsService

router = APIRouter(tags=["owner-compliance"])


@router.get("/outlets/{outlet_id}/audit-log", response_model=AuditLogListResponse)
async def list_audit_log(
    outlet_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=200),
    owner: BusinessOwner = Depends(require_permission(PERM_AUDIT_VIEW)),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    return await ComplianceQueryService(db).list_audit(owner, outlet_id, limit)


@router.get("/outlets/{outlet_id}/pos/discount-policy", response_model=DiscountPolicyResponse)
async def discount_policy(
    outlet_id: uuid.UUID,
    owner: BusinessOwner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> DiscountPolicyResponse:
    pos = await BusinessSettingsService(db).get_pos_settings(owner.business_id)
    return DiscountPolicyResponse(
        worker_max_discount_percent=pos.worker_max_discount_percent,
        max_discount_percent=pos.max_discount_percent,
        manager_pin_configured=pos.manager_pin_hash is not None,
    )


@router.post("/outlets/{outlet_id}/pos/bills/{bill_id}/refunds", response_model=RefundResponse)
async def refund_bill(
    outlet_id: uuid.UUID,
    bill_id: uuid.UUID,
    body: RefundCreateRequest,
    owner: BusinessOwner = Depends(require_permission(PERM_POS_REFUND)),
    db: AsyncSession = Depends(get_db),
) -> RefundResponse:
    return await RefundService(db).create_refund(owner, outlet_id, bill_id, body)


@router.get(
    "/outlets/{outlet_id}/pos/bills/{bill_id}/invoice",
    response_class=HTMLResponse,
)
async def bill_invoice_html(
    outlet_id: uuid.UUID,
    bill_id: uuid.UUID,
    owner: BusinessOwner = Depends(require_permission(PERM_POS_BILLS)),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    html = await InvoiceService(db).render_invoice_html(owner, outlet_id, bill_id)
    return HTMLResponse(content=html)
