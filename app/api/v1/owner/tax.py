from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.permissions import require_any_permission, require_permission
from app.db.deps import get_db
from app.models.tenant import BusinessOwner
from app.schemas.owner.tax import (
    TaxCatalogResponse,
    TaxPreviewRequest,
    TaxPreviewResponse,
    TaxProfileCreate,
    TaxProfileResponse,
    TaxProfileUpdate,
)
from app.services.owner.permissions import PERM_TAX_EDIT, PERM_TAX_VIEW
from app.services.owner.tax_service import OwnerTaxService

router = APIRouter(prefix="/outlets/{outlet_id}/tax", tags=["owner-tax"])

_view = Depends(require_any_permission(PERM_TAX_VIEW, PERM_TAX_EDIT))
_edit = Depends(require_permission(PERM_TAX_EDIT))


class TaxEnabledBody(BaseModel):
    enabled: bool


@router.get("", response_model=list[TaxProfileResponse])
async def list_tax_profiles(
    outlet_id: uuid.UUID,
    owner: BusinessOwner = _view,
    db: AsyncSession = Depends(get_db),
) -> list[TaxProfileResponse]:
    return await OwnerTaxService(db).list_profiles(owner, outlet_id)


@router.get("/catalog", response_model=TaxCatalogResponse)
async def tax_catalog(
    outlet_id: uuid.UUID,
    owner: BusinessOwner = _view,
    db: AsyncSession = Depends(get_db),
) -> TaxCatalogResponse:
    return await OwnerTaxService(db).catalog(owner, outlet_id)


@router.post("/preview", response_model=TaxPreviewResponse)
async def tax_preview(
    outlet_id: uuid.UUID,
    body: TaxPreviewRequest,
    owner: BusinessOwner = _view,
    db: AsyncSession = Depends(get_db),
) -> TaxPreviewResponse:
    return await OwnerTaxService(db).preview(owner, outlet_id, body)


@router.put("/enabled", response_model=list[TaxProfileResponse])
async def set_tax_enabled(
    outlet_id: uuid.UUID,
    body: TaxEnabledBody,
    owner: BusinessOwner = _edit,
    db: AsyncSession = Depends(get_db),
) -> list[TaxProfileResponse]:
    return await OwnerTaxService(db).set_enabled(owner, outlet_id, body.enabled)


@router.post("", response_model=TaxProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_tax_profile(
    outlet_id: uuid.UUID,
    body: TaxProfileCreate,
    owner: BusinessOwner = _edit,
    db: AsyncSession = Depends(get_db),
) -> TaxProfileResponse:
    return await OwnerTaxService(db).create(owner, outlet_id, body)


@router.patch("/{profile_id}", response_model=TaxProfileResponse)
async def update_tax_profile(
    outlet_id: uuid.UUID,
    profile_id: uuid.UUID,
    body: TaxProfileUpdate,
    owner: BusinessOwner = _edit,
    db: AsyncSession = Depends(get_db),
) -> TaxProfileResponse:
    return await OwnerTaxService(db).update(owner, outlet_id, profile_id, body)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tax_profile(
    outlet_id: uuid.UUID,
    profile_id: uuid.UUID,
    owner: BusinessOwner = _edit,
    db: AsyncSession = Depends(get_db),
) -> None:
    await OwnerTaxService(db).delete(owner, outlet_id, profile_id)
