from __future__ import annotations

import re
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import generate_secure_password, hash_password, verify_password
from app.models.enums import TenantStatus
from app.models.platform_admin import PlatformAuditLog, PlatformAdmin
from app.models.tenant import Business, BusinessOwner, Outlet
from app.schemas.platform.onboarding import (
    TenantOnboardingCreateRequest,
    TenantOnboardingCreateResponse,
    TenantStatusUpdateRequest,
    TenantSummary,
    OwnerCredentialsOnce,
)


def _slugify(value: str) -> str:
    lowered = value.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug[:40] or "tenant"


def _generate_ref_code() -> str:
    year = datetime.now(timezone.utc).strftime("%y")
    suffix = secrets.token_hex(3).upper()
    return f"KHB-{year}{suffix}"


async def _unique_owner_username(db: AsyncSession, business_name: str) -> str:
    base = _slugify(business_name).replace("-", "")[:12]
    for _ in range(10):
        candidate = f"owner.{base}.{secrets.token_hex(2)}"
        exists = await db.execute(
            select(BusinessOwner.id).where(BusinessOwner.username == candidate),
        )
        if exists.scalar_one_or_none() is None:
            return candidate
    raise HTTPException(status_code=500, detail="Could not allocate owner username")


class PlatformOnboardingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_tenant(
        self,
        payload: TenantOnboardingCreateRequest,
        admin: PlatformAdmin,
    ) -> TenantOnboardingCreateResponse:
        owner_email = str(payload.owner.email).lower()
        dup = await self.db.execute(
            select(BusinessOwner.id).where(
                (BusinessOwner.email == owner_email)
                | (BusinessOwner.mobile == payload.owner.mobile),
            ),
        )
        if dup.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Owner email or mobile already registered",
            )

        ref_code = _generate_ref_code()
        ref_exists = await self.db.execute(select(Outlet.id).where(Outlet.ref_code == ref_code))
        if ref_exists.scalar_one_or_none():
            ref_code = _generate_ref_code()

        tenant_status = (
            TenantStatus.ACTIVE
            if payload.business.activate_immediately
            else TenantStatus.DRAFT
        )

        business = Business(
            legal_name=payload.business.legal_name.strip(),
            business_type=payload.business.business_type,
            primary_phone=payload.business.primary_phone,
            primary_email=str(payload.business.primary_email).lower(),
            city=payload.business.city.strip(),
            state=payload.business.state.strip(),
            gst_registered=payload.business.gst_registered,
            gstin=payload.business.gstin,
            fssai=payload.business.fssai,
            pan=payload.business.pan,
            plan_tier=payload.business.plan_tier,
            status=tenant_status,
            internal_notes=payload.business.internal_notes,
            onboarded_by_admin_id=admin.id,
        )
        self.db.add(business)
        await self.db.flush()

        outlet = Outlet(
            business_id=business.id,
            name=payload.outlet.name.strip(),
            address_line=payload.outlet.address_line.strip(),
            pincode=payload.outlet.pincode.strip(),
            outlet_phone=payload.outlet.outlet_phone,
            operating_models=[m.value for m in payload.outlet.operating_models],
            venue_kinds=[k.value for k in payload.outlet.venue_kinds],
            time_based_billing_enabled=payload.outlet.time_based_billing_enabled,
            rough_scale_notes=payload.outlet.rough_scale_notes,
            ref_code=ref_code,
            status=tenant_status,
        )
        self.db.add(outlet)

        temp_password = generate_secure_password(16)
        username = await _unique_owner_username(self.db, payload.business.legal_name)
        password_hash = hash_password(temp_password)
        if not verify_password(temp_password, password_hash):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not generate owner credentials",
            )
        owner = BusinessOwner(
            business_id=business.id,
            full_name=payload.owner.full_name.strip(),
            email=str(payload.owner.email).lower(),
            mobile=payload.owner.mobile,
            username=username,
            password_hash=password_hash,
            must_change_password=True,
            is_active=True,
        )
        self.db.add(owner)

        audit = PlatformAuditLog(
            admin_id=admin.id,
            action="tenant_onboarded",
            resource_type="business",
            resource_id=str(business.id),
            metadata_json=(
                f'{{"outlet_ref":"{ref_code}","owner_username":"{username}"}}'
            ),
        )
        self.db.add(audit)
        await self.db.commit()
        await self.db.refresh(business)
        await self.db.refresh(outlet)
        await self.db.refresh(owner)

        return TenantOnboardingCreateResponse(
            business_id=business.id,
            outlet_id=outlet.id,
            owner_id=owner.id,
            outlet_ref_code=outlet.ref_code,
            status=business.status,
            owner_credentials=OwnerCredentialsOnce(
                username=username,
                temporary_password=temp_password,
            ),
        )

    async def list_tenants(self) -> list[TenantSummary]:
        result = await self.db.execute(
            select(Business)
            .options(selectinload(Business.outlets))
            .order_by(Business.created_at.desc()),
        )
        businesses = result.scalars().all()
        summaries: list[TenantSummary] = []
        for business in businesses:
            outlet = business.outlets[0] if business.outlets else None
            if outlet is None:
                continue
            summaries.append(
                TenantSummary(
                    business_id=business.id,
                    legal_name=business.legal_name,
                    status=business.status,
                    plan_tier=business.plan_tier,
                    primary_email=business.primary_email,
                    city=business.city,
                    state=business.state,
                    outlet_ref_code=outlet.ref_code,
                    outlet_name=outlet.name,
                    created_at=business.created_at.isoformat(),
                ),
            )
        return summaries

    async def update_tenant_status(
        self,
        business_id: uuid.UUID,
        payload: TenantStatusUpdateRequest,
        admin: PlatformAdmin,
    ) -> TenantSummary:
        result = await self.db.execute(
            select(Business)
            .where(Business.id == business_id)
            .options(selectinload(Business.outlets)),
        )
        business = result.scalar_one_or_none()
        if business is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

        if payload.status == TenantStatus.SUSPENDED:
            if not payload.confirm_username or not payload.confirm_password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Re-authentication required to suspend",
                )
            if payload.confirm_username.strip().lower() != admin.username:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid confirmation credentials",
                )
            if not verify_password(payload.confirm_password, admin.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid confirmation credentials",
                )

        business.status = payload.status
        for outlet in business.outlets:
            outlet.status = payload.status

        audit = PlatformAuditLog(
            admin_id=admin.id,
            action="tenant_status_updated",
            resource_type="business",
            resource_id=str(business.id),
            metadata_json=f'{{"status":"{payload.status.value}"}}',
        )
        self.db.add(audit)
        await self.db.commit()
        await self.db.refresh(business)

        outlet = business.outlets[0]
        return TenantSummary(
            business_id=business.id,
            legal_name=business.legal_name,
            status=business.status,
            plan_tier=business.plan_tier,
            primary_email=business.primary_email,
            city=business.city,
            state=business.state,
            outlet_ref_code=outlet.ref_code,
            outlet_name=outlet.name,
            created_at=business.created_at.isoformat(),
        )
