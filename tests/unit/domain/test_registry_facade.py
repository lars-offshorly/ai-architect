from __future__ import annotations

from pathlib import Path

from catalog.bundle_catalog import BundleCatalog
from domain.services.canonical_bundle_resolver import CanonicalBundleResolver
from domain.services.canonical_manifest_registry import CanonicalManifestRegistry
from domain.services.canonical_metadata_service import CanonicalMetadataService
from domain.services.canonical_payload_builder import CanonicalPayloadBuilder
from domain.services.registry_facade import RegistryFacade


def _facade(allow_fallback: bool = False) -> RegistryFacade:
    root = Path(__file__).resolve().parents[3]
    registry = CanonicalManifestRegistry(root / "new_json_samples")
    return RegistryFacade(
        resolver=CanonicalBundleResolver(registry, strict_mapping=True),
        payload_builder=CanonicalPayloadBuilder(registry),
        metadata_service=CanonicalMetadataService(registry),
        allow_registry_module_fallback=allow_fallback,
    )


def test_list_supported_bundles_from_canonical_mapping() -> None:
    supported = _facade().list_supported_bundles()
    assert "ticketing" in supported
    assert "construction" in supported
    assert "hr_management" in supported


def test_inferred_modules_default_to_canonical_map() -> None:
    modules = _facade().inferred_modules_for_bundle("ticketing")
    assert modules == ["tickets", "kpi", "dashboard"]


def test_inferred_modules_can_fallback_to_registry_when_enabled(shared_catalog: BundleCatalog) -> None:
    facade = _facade(allow_fallback=True)
    facade.catalog_fallback = shared_catalog
    modules = facade.inferred_modules_for_bundle("ticketing")
    assert modules  # from registry default_modules


def test_get_raw_manifest_for_generic_aliases_to_ticketing() -> None:
    """The synthetic generic bundle reuses the BPO/ticketing manifest."""
    facade = _facade()
    generic_manifest = facade.get_raw_manifest("generic")
    ticketing_manifest = facade.get_raw_manifest("ticketing")
    assert generic_manifest is not None
    assert generic_manifest == ticketing_manifest
