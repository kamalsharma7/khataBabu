from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.compliance import PosBillRefund
from app.models.enums import BillStatus, OwnerRole
from app.models.order import PosBill, PosOrder
from app.models.tenant import BusinessOwner
from app.schemas.owner.settings import RefundCreateRequest, RefundResponse
from app.services.owner.access import get_outlet_for_owner
from app.services.owner.audit_service import TenantAuditService
from app.services.owner.business_settings_service import BusinessSettingsService
from app.services.owner.order_pricing import money
from app.services.owner.permissions import PERM_POS_REFUND, has_permission


class RefundService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.audit = TenantAuditService(db)
        self.settings = BusinessSettingsService(db)

    async def create_refund(
        self,
        owner: BusinessOwner,
        outlet_id: uuid.UUID,
        bill_id: uuid.UUID,
        payload: RefundCreateRequest,
    ) -> RefundResponse:
        if not has_permission(owner.role, PERM_POS_REFUND):
            if owner.role in (OwnerRole.WORKER, OwnerRole.EMPLOYEE):
                raise HTTPException(status_code=403, detail="Refunds require manager access")
        await get_outlet_for_owner(self.db, owner, outlet_id)
        result = await self.db.execute(
            select(PosBill)
            .where(PosBill.id == bill_id, PosBill.outlet_id == outlet_id)
            .options(selectinload(PosBill.payments)),
        )
        bill = result.scalar_one_or_none()
        if bill is None:
            raise HTTPException(status_code=404, detail="Bill not found")
        if bill.status != BillStatus.SETTLED:
            raise HTTPException(status_code=400, detail="Only settled bills can be refunded")
        amount = money(payload.amount)
        remaining = money(bill.grand_total - bill.refunded_total)
        if amount > remaining:
            raise HTTPException(
                status_code=400,
                detail=f"Refund cannot exceed remaining {remaining}",
            )
        if owner.role in (OwnerRole.WORKER, OwnerRole.EMPLOYEE):
            ok = await self.settings.verify_manager_pin(owner.business_id, payload.manager_approval_pin)
            if not ok:
                raise HTTPException(
                    status_code=403,
                    detail="Manager approval PIN required for refunds",
                )
        approved_by = owner.id
        refund = PosBillRefund(
            bill_id=bill.id,
            outlet_id=outlet_id,
            amount=amount,
            method=payload.method,
            reason=payload.reason.strip(),
            created_by_owner_id=owner.id,
            approved_by_owner_id=approved_by,
            created_at=datetime.now(timezone.utc),
        )
        bill.refunded_total = money(bill.refunded_total + amount)
        self.db.add(refund)
        order_customer_id = (
            await self.db.execute(select(PosOrder.customer_id).where(PosOrder.id == bill.order_id))
        ).scalar_one_or_none()
        if order_customer_id is not None:
            from app.services.owner.customer_service import OwnerCustomerService

            await self.db.flush()
            await OwnerCustomerService(self.db).refresh_stats(order_customer_id)
        await self.audit.log(
            business_id=owner.business_id,
            outlet_id=outlet_id,
            actor=owner,
            action="bill.refund",
            entity_type="bill",
            entity_id=str(bill.id),
            summary=f"Refund ₹{amount} on bill #{bill.bill_number}",
            detail={"method": payload.method, "amount": str(amount)},
            reason=payload.reason,
        )
        await self.db.commit()
        return RefundResponse(
            id=str(refund.id),
            bill_id=str(bill.id),
            amount=amount,
            method=refund.method,
            reason=refund.reason,
            refunded_total=bill.refunded_total,
            bill_grand_total=bill.grand_total,
            created_at=refund.created_at.isoformat(),
        )
