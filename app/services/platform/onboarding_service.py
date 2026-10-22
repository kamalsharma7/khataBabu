from __future__ import annotations

import re
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import generate_secure_password, hash_password, verify_password
from app.models.enums import (
    OperatingModel,
    OwnerRole,
    SalesEmploymentStatus,
    TenantStatus,
    VenueKind,
)
from app.models.platform_admin import PlatformAuditLog, PlatformAdmin
from app.models.platform_sales import PlatformSalesEmployee
from app.models.tenant import Business, BusinessOwner, Outlet
from app.schemas.platform.onboarding import (
    OwnerCredentialsOnce,
    TenantDetailResponse,
    TenantOnboardingCreateRequest,
    TenantOnboardingCreateResponse,
    TenantOwnerSummary,
    TenantStatusUpdateRequest,
    TenantSummary,
    TenantUpdateRequest,
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


async def _unique_staff_placeholder_mobile(db: AsyncSession) -> str:
    """Staff POS logins do not need a real phone; mobile must be unique in business_owners."""
    for _ in range(20):
        suffix = f"{secrets.randbelow(10 ** 8):08d}"
        candidate = f"+9199{suffix}"
        exists = await db.execute(
            select(BusinessOwner.id).where(BusinessOwner.mobile == candidate),
        )
        if exists.scalar_one_or_none() is None:
            return candidate
    raise HTTPException(status_code=500, detail="Could not allocate staff mobile placeholder")


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

        if payload.assigned_sales_employee_id:
            sales_check = await self.db.execute(
                select(PlatformSalesEmployee.id).where(
                    PlatformSalesEmployee.id == payload.assigned_sales_employee_id,
                    PlatformSalesEmployee.employment_status == SalesEmploymentStatus.ACTIVE,
                ),
            )
            if sales_check.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid sales employee",
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
            assigned_sales_employee_id=payload.assigned_sales_employee_id,
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
            role=OwnerRole.OWNER,
            is_active=True,
        )
        self.db.add(owner)

        staff_credentials: list[OwnerCredentialsOnce] = []
        staff_credentials.append(
            await self._create_staff_login(
                business,
                role=OwnerRole.EMPLOYEE,
                label="receptionist",
                full_name="Receptionist",
            ),
        )

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
        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            err = str(exc.orig) if exc.orig else str(exc)
            if "uq_business_owners_mobile" in err or "uq_business_owners_email" in err:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Owner email or mobile already registered",
                ) from exc
            if "uq_business_owners_username" in err:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Could not allocate a unique owner username; try again",
                ) from exc
            raise

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
                role=OwnerRole.OWNER.value,
            ),
            staff_credentials=staff_credentials,
        )

    async def _create_staff_login(
        self,
        business: Business,
        role: OwnerRole,
        label: str,
        full_name: str | None = None,
    ) -> OwnerCredentialsOnce:
        temp_password = generate_secure_password(14)
        username = await _unique_owner_username(self.db, f"{business.legal_name}-{label}")
        password_hash = hash_password(temp_password)
        staff_mobile = await _unique_staff_placeholder_mobile(self.db)
        display = full_name or f"{business.legal_name} {label}"
        staff = BusinessOwner(
            business_id=business.id,
            full_name=display,
            email=f"{label}-{secrets.token_hex(3)}@staff.khatababu.local",
            mobile=staff_mobile,
            username=username,
            password_hash=password_hash,
            must_change_password=True,
            role=role,
            is_active=True,
        )
        self.db.add(staff)
        return OwnerCredentialsOnce(
            username=username,
            temporary_password=temp_password,
            role=role.value,
        )

    async def _business_detail(
        self,
        business: Business,
        outlet: Outlet,
        owner: BusinessOwner,
        sales_name: str | None,
    ) -> TenantDetailResponse:
        return TenantDetailResponse(
            business_id=business.id,
            outlet_id=outlet.id,
            status=business.status,
            legal_name=business.legal_name,
            business_type=business.business_type,
            primary_phone=business.primary_phone,
            primary_email=business.primary_email,
            city=business.city,
            state=business.state,
            gst_registered=business.gst_registered,
            gstin=business.gstin,
            fssai=business.fssai,
            pan=business.pan,
            plan_tier=business.plan_tier,
            internal_notes=business.internal_notes,
            assigned_sales_employee_id=business.assigned_sales_employee_id,
            assigned_sales_employee_name=sales_name,
            outlet_name=outlet.name,
            address_line=outlet.address_line,
            pincode=outlet.pincode,
            outlet_phone=outlet.outlet_phone,
            operating_models=[OperatingModel(m) for m in outlet.operating_models],
            venue_kinds=[VenueKind(k) for k in outlet.venue_kinds],
            time_based_billing_enabled=outlet.time_based_billing_enabled,
            rough_scale_notes=outlet.rough_scale_notes,
            outlet_ref_code=outlet.ref_code,
            owner=TenantOwnerSummary(
                id=owner.id,
                full_name=owner.full_name,
                email=owner.email,
                mobile=owner.mobile,
                username=owner.username,
                role=owner.role.value if hasattr(owner.role, "value") else str(owner.role),
            ),
            created_at=business.created_at.isoformat(),
        )

    async def get_tenant_detail(self, business_id: uuid.UUID) -> TenantDetailResponse:
        result = await self.db.execute(
            select(Business)
            .where(Business.id == business_id)
            .options(selectinload(Business.outlets), selectinload(Business.owners)),
        )
        business = result.scalar_one_or_none()
        if business is None or not business.outlets:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
        outlet = business.outlets[0]
        owner = next((o for o in business.owners if o.role == OwnerRole.OWNER), None)
        if owner is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Owner not found")
        sales_name: str | None = None
        if business.assigned_sales_employee_id:
            sales_row = await self.db.execute(
                select(PlatformSalesEmployee.full_name).where(
                    PlatformSalesEmployee.id == business.assigned_sales_employee_id,
                ),
            )
            sales_name = sales_row.scalar_one_or_none()
        return await self._business_detail(business, outlet, owner, sales_name)

    async def update_tenant(
        self,
        business_id: uuid.UUID,
        payload: TenantUpdateRequest,
        admin: PlatformAdmin,
    ) -> TenantDetailResponse:
        result = await self.db.execute(
            select(Business)
            .where(Business.id == business_id)
            .options(selectinload(Business.outlets), selectinload(Business.owners)),
        )
        business = result.scalar_one_or_none()
        if business is None or not business.outlets:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
        outlet = business.outlets[0]
        owner = next((o for o in business.owners if o.role == OwnerRole.OWNER), None)
        if owner is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Owner not found")

        if payload.legal_name is not None:
            business.legal_name = payload.legal_name.strip()
        if payload.business_type is not None:
            business.business_type = payload.business_type
        if payload.primary_phone is not None:
            business.primary_phone = payload.primary_phone
        if payload.primary_email is not None:
            business.primary_email = str(payload.primary_email).lower()
        if payload.city is not None:
            business.city = payload.city.strip()
        if payload.state is not None:
            business.state = payload.state.strip()
        if payload.gst_registered is not None:
            business.gst_registered = payload.gst_registered
        if payload.gstin is not None:
            business.gstin = payload.gstin.strip().upper() if payload.gstin else None
        if payload.fssai is not None:
            business.fssai = payload.fssai.strip() or None
        if payload.pan is not None:
            business.pan = payload.pan.strip().upper() or None
        if payload.plan_tier is not None:
            business.plan_tier = payload.plan_tier
        if payload.internal_notes is not None:
            business.internal_notes = payload.internal_notes.strip() or None
        if payload.assigned_sales_employee_id is not None:
            if payload.assigned_sales_employee_id:
                sales_check = await self.db.execute(
                    select(PlatformSalesEmployee.id).where(
                        PlatformSalesEmployee.id == payload.assigned_sales_employee_id,
                    ),
                )
                if sales_check.scalar_one_or_none() is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid sales employee",
                    )
            business.assigned_sales_employee_id = payload.assigned_sales_employee_id

        if payload.outlet_name is not None:
            outlet.name = payload.outlet_name.strip()
        if payload.address_line is not None:
            outlet.address_line = payload.address_line.strip()
        if payload.pincode is not None:
            outlet.pincode = payload.pincode.strip()
        if payload.outlet_phone is not None:
            outlet.outlet_phone = payload.outlet_phone
        if payload.operating_models is not None:
            outlet.operating_models = [m.value for m in payload.operating_models]
        if payload.venue_kinds is not None:
            outlet.venue_kinds = [k.value for k in payload.venue_kinds]
        if payload.time_based_billing_enabled is not None:
            outlet.time_based_billing_enabled = payload.time_based_billing_enabled
        if payload.rough_scale_notes is not None:
            outlet.rough_scale_notes = payload.rough_scale_notes.strip() or None

        if payload.owner_full_name is not None:
            owner.full_name = payload.owner_full_name.strip()
        if payload.owner_email is not None:
            owner.email = str(payload.owner_email).lower()
        if payload.owner_mobile is not None:
            owner.mobile = payload.owner_mobile

        audit = PlatformAuditLog(
            admin_id=admin.id,
            action="tenant_updated",
            resource_type="business",
            resource_id=str(business.id),
            metadata_json="{}",
        )
        self.db.add(audit)
        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            err = str(exc.orig) if exc.orig else str(exc)
            if "uq_business_owners_mobile" in err or "uq_business_owners_email" in err:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Owner email or mobile already in use",
                ) from exc
            raise
        await self.db.refresh(business)
        await self.db.refresh(outlet)
        await self.db.refresh(owner)
        return await self.get_tenant_detail(business_id)

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
