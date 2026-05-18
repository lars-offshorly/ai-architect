from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from api.routers.bundles import get_bundle_metadata
from api.schemas.bundle_metadata import BundleMetadataResponseSchema
from domain.services.canonical_bundle_resolver import CanonicalBundleResolver
from domain.services.canonical_manifest_registry import CanonicalManifestRegistry
from domain.services.canonical_metadata_service import CanonicalMetadataService
from domain.services.canonical_payload_builder import CanonicalPayloadBuilder
from domain.services.registry_facade import RegistryFacade


def test_get_bundle_metadata_returns_existing_bundle_metadata() -> None:
    root = Path(__file__).resolve().parents[3]
    registry = CanonicalManifestRegistry(root / "new_json_samples")
    facade = RegistryFacade(
        resolver=CanonicalBundleResolver(registry, strict_mapping=True),
        payload_builder=CanonicalPayloadBuilder(registry),
        metadata_service=CanonicalMetadataService(registry),
    )

    metadata = get_bundle_metadata(
        bundle_key="ticketing",
        registry_facade=facade,
    )

    assert isinstance(metadata, BundleMetadataResponseSchema)
    assert metadata.bundle_key == "ticketing"
    assert metadata.kpis


def test_get_bundle_metadata_raises_404_for_unknown_bundle() -> None:
    root = Path(__file__).resolve().parents[3]
    registry = CanonicalManifestRegistry(root / "new_json_samples")
    facade = RegistryFacade(
        resolver=CanonicalBundleResolver(registry, strict_mapping=True),
        payload_builder=CanonicalPayloadBuilder(registry),
        metadata_service=CanonicalMetadataService(registry),
    )

    with pytest.raises(HTTPException) as exc:
        get_bundle_metadata(
            bundle_key="unknown_bundle",
            registry_facade=facade,
        )

    assert exc.value.status_code == 404
