from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.compliance import BusinessPosSettings
from app.models.tenant import Business, BusinessOwner
from app.schemas.owner.settings import (
    BusinessProfileUpdate,
    BusinessSettingsResponse,
    ManagerPinUpdate,
    PosPolicyUpdate,
)
from app.services.owner.audit_service import TenantAuditService
from app.services.owner.permissions import has_permission, PERM_SETTINGS_ALL, PERM_SETTINGS_VIEW


class BusinessSettingsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.audit = TenantAuditService(db)

    async def _settings_row(self, business_id: uuid.UUID) -> BusinessPosSettings:
        result = await self.db.execute(
            select(BusinessPosSettings).where(BusinessPosSettings.business_id == business_id),
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = BusinessPosSettings(business_id=business_id)
            self.db.add(row)
            await self.db.flush()
        return row

    async def get_settings(self, owner: BusinessOwner) -> BusinessSettingsResponse:
        if not has_permission(owner.role, PERM_SETTINGS_VIEW):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access")
        business = await self.db.get(Business, owner.business_id)
        if business is None:
            raise HTTPException(status_code=404, detail="Business not found")
        pos = await self._settings_row(business.id)
        return self._to_response(business, pos)

    def _to_response(self, business: Business, pos: BusinessPosSettings) -> BusinessSettingsResponse:
        return BusinessSettingsResponse(
            legal_name=business.legal_name,
            trading_name=pos.trading_name,
            primary_phone=business.primary_phone,
            primary_email=business.primary_email,
            city=business.city,
            state=business.state,
            gst_registered=business.gst_registered,
            gstin=business.gstin,
            fssai=business.fssai,
            pan=business.pan,
            registered_address=pos.registered_address,
            invoice_prefix=pos.invoice_prefix,
            worker_max_discount_percent=pos.worker_max_discount_percent,
            max_discount_percent=pos.max_discount_percent,
            manager_pin_configured=pos.manager_pin_hash is not None,
        )

    async def update_profile(
        self,
        owner: BusinessOwner,
        payload: BusinessProfileUpdate,
    ) -> BusinessSettingsResponse:
        if not has_permission(owner.role, PERM_SETTINGS_ALL):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner only")
        business = await self.db.get(Business, owner.business_id)
        if business is None:
            raise HTTPException(status_code=404, detail="Business not found")
        pos = await self._settings_row(business.id)
        data = payload.model_dump(exclude_unset=True)
        for key in ("legal_name", "primary_phone", "primary_email", "city", "state", "gst_registered", "gstin", "fssai", "pan"):
            if key in data:
                setattr(business, key, data[key])
        for key in ("trading_name", "registered_address", "invoice_prefix"):
            if key in data:
                setattr(pos, key, data[key])
        await self.audit.log(
            business_id=business.id,
            outlet_id=None,
            actor=owner,
            action="settings.update",
            entity_type="business",
            entity_id=str(business.id),
            summary="Updated business profile and invoice settings",
            detail=data,
        )
        await self.db.commit()
        await self.db.refresh(business)
        await self.db.refresh(pos)
        return self._to_response(business, pos)

    async def update_policy(self, owner: BusinessOwner, payload: PosPolicyUpdate) -> BusinessSettingsResponse:
        if not has_permission(owner.role, PERM_SETTINGS_ALL):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner only")
        business = await self.db.get(Business, owner.business_id)
        pos = await self._settings_row(owner.business_id)
        pos.worker_max_discount_percent = payload.worker_max_discount_percent
        pos.max_discount_percent = payload.max_discount_percent
        await self.audit.log(
            business_id=owner.business_id,
            outlet_id=None,
            actor=owner,
            action="settings.policy",
            entity_type="business",
            entity_id=str(owner.business_id),
            summary="Updated discount policy",
            detail=payload.model_dump(),
        )
        await self.db.commit()
        await self.db.refresh(pos)
        return self._to_response(business, pos)

    async def set_manager_pin(self, owner: BusinessOwner, payload: ManagerPinUpdate) -> BusinessSettingsResponse:
        if not has_permission(owner.role, PERM_SETTINGS_ALL):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner only")
        business = await self.db.get(Business, owner.business_id)
        pos = await self._settings_row(owner.business_id)
        pos.manager_pin_hash = hash_password(payload.pin.strip())
        await self.audit.log(
            business_id=owner.business_id,
            outlet_id=None,
            actor=owner,
            action="settings.manager_pin",
            entity_type="business",
            entity_id=str(owner.business_id),
            summary="Manager approval PIN updated",
        )
        await self.db.commit()
        return self._to_response(business, pos)

    async def verify_manager_pin(self, business_id: uuid.UUID, pin: str | None) -> bool:
        if not pin or not pin.strip():
            return False
        pos = await self._settings_row(business_id)
        if pos.manager_pin_hash is None:
            return False
        return verify_password(pin.strip(), pos.manager_pin_hash)

    async def get_pos_settings(self, business_id: uuid.UUID) -> BusinessPosSettings:
        return await self._settings_row(business_id)
