from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_registry_facade
from domain.models.bundle_metadata import BundleMetadata
from domain.services.registry_facade import RegistryFacade

router = APIRouter(prefix="/bundles", tags=["bundles"])


@router.get("/{bundle_key}/metadata", response_model=BundleMetadata)
def get_bundle_metadata(
    bundle_key: str,
    registry_facade: Annotated[RegistryFacade, Depends(get_registry_facade)],
) -> BundleMetadata:
    if bundle_key not in registry_facade.list_supported_bundles():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bundle not found: {bundle_key}",
        )
    return registry_facade.get_bundle_metadata(bundle_key)
