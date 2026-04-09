from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_bundle_catalog, get_bundle_metadata_service
from catalog.bundle_catalog import BundleCatalog
from domain.models.bundle_metadata import BundleMetadata
from domain.services.bundle_metadata import BundleMetadataService

router = APIRouter(prefix="/bundles", tags=["bundles"])


@router.get("/{bundle_key}/metadata", response_model=BundleMetadata)
def get_bundle_metadata(
    bundle_key: str,
    metadata_service: Annotated[
        BundleMetadataService, Depends(get_bundle_metadata_service)
    ],
    catalog: Annotated[BundleCatalog, Depends(get_bundle_catalog)],
) -> BundleMetadata:
    if catalog.get(bundle_key) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bundle not found: {bundle_key}",
        )
    return metadata_service.get_metadata(bundle_key)
