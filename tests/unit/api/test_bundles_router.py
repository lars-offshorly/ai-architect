from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from api.routers.bundles import get_bundle_metadata
from catalog.bundle_catalog import BundleCatalog
from domain.models.bundle_metadata import BundleMetadata
from domain.services.bundle_metadata import BundleMetadataService

REGISTRY_PATH = (
    Path(__file__).resolve().parents[3] / "src/templates/bundle_registry.yaml"
)


def test_get_bundle_metadata_returns_existing_bundle_metadata(shared_catalog: BundleCatalog) -> None:
    service = BundleMetadataService(shared_catalog)

    metadata = get_bundle_metadata(
        bundle_key="hr_management",
        metadata_service=service,
        catalog=shared_catalog,
    )

    assert isinstance(metadata, BundleMetadata)
    assert metadata.bundle_key == "hr_management"
    assert metadata.kpis


def test_get_bundle_metadata_raises_404_for_unknown_bundle(shared_catalog: BundleCatalog) -> None:
    service = BundleMetadataService(shared_catalog)

    with pytest.raises(HTTPException) as exc:
        get_bundle_metadata(
            bundle_key="unknown_bundle",
            metadata_service=service,
            catalog=shared_catalog,
        )

    assert exc.value.status_code == 404
